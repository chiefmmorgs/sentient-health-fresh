"""
Essential tests for OutputFixingParser class.
Focuses on core functionality without redundant test cases.
"""

import pytest
from unittest.mock import MagicMock, patch

from sentientresearchagent.hierarchical_agent_framework.agents.utils import OutputFixingParser, JsonFixingResponse, FixingAttempt


class TestModel:
    """Simple test model that mimics Pydantic behavior."""
    def __init__(self, name: str, value: int, active: bool = True):
        self.name = name
        self.value = value
        self.active = active
    
    @classmethod
    def model_validate_json(cls, json_str: str):
        """Mock Pydantic's model_validate_json method."""
        import json
        data = json.loads(json_str)
        return cls(**data)


class TestOutputFixingParser:
    """Core tests for OutputFixingParser functionality."""

    def setup_method(self):
        """Setup parser for each test."""
        self.parser = OutputFixingParser(
            model_id="test-model",
            max_llm_retries=2,
            max_previous_attempts_in_context=1
        )

    def test_initialization(self):
        """Test parser initialization."""
        assert self.parser.model_id == "test-model"
        assert self.parser.max_llm_retries == 2
        assert self.parser.max_previous_attempts_in_context == 1
        assert "JSON repair specialist" in self.parser.SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_direct_parsing_success(self):
        """Test successful direct JSON parsing."""
        valid_json = '{"name": "test", "value": 123, "active": true}'
        
        result = await self.parser.parse(valid_json, TestModel, use_llm_fixing=False)
        
        assert result is not None
        assert result.name == "test"
        assert result.value == 123
        assert result.active is True

    @pytest.mark.asyncio 
    async def test_json_repair_fallback(self):
        """Test json_repair fallback for malformed JSON."""
        malformed_json = '{"name": "test", "value": 123, "active": true,}'  # trailing comma
        
        result = await self.parser.parse(malformed_json, TestModel, use_llm_fixing=False)
        
        assert result is not None
        assert result.name == "test"
        assert result.value == 123

    @pytest.mark.asyncio
    async def test_markdown_extraction(self):
        """Test JSON extraction from markdown code blocks."""
        markdown_text = '''
        ```json
        {"name": "markdown_test", "value": 456}
        ```
        '''
        
        result = await self.parser.parse(markdown_text, TestModel, use_llm_fixing=False)
        
        assert result is not None
        assert result.name == "markdown_test"
        assert result.value == 456

    @pytest.mark.asyncio
    async def test_bracket_detection(self):
        """Test JSON extraction using bracket detection."""
        text_with_json = 'Some text {"name": "bracket_test", "value": 789} more text'
        
        result = await self.parser.parse(text_with_json, TestModel, use_llm_fixing=False)
        
        assert result is not None
        assert result.name == "bracket_test"
        assert result.value == 789

    @pytest.mark.asyncio
    async def test_all_strategies_fail(self):
        """Test when all non-LLM strategies fail."""
        invalid_content = "This is not JSON at all"
        
        result = await self.parser.parse(invalid_content, TestModel, use_llm_fixing=False)
        
        assert result is None

    @pytest.mark.asyncio
    @patch('sentientresearchagent.hierarchical_agent_framework.agents.utils.litellm.acompletion')
    async def test_llm_fixing_success(self, mock_litellm):
        """Test successful LLM-based JSON fixing."""
        # Setup mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''{
            "rationale": "Fixed missing quotes around keys",
            "fixed_json": "{\\"name\\": \\"fixed_test\\", \\"value\\": 555, \\"active\\": true}"
        }'''
        mock_litellm.return_value = mock_response
        
        malformed_json = 'This is completely invalid JSON that contains: name=broken_test, value=555'
        
        result = await self.parser.parse(malformed_json, TestModel, use_llm_fixing=True)
        
        assert result is not None
        assert result.name == "fixed_test"
        assert result.value == 555
        mock_litellm.assert_called_once()

    @pytest.mark.asyncio
    @patch('sentientresearchagent.hierarchical_agent_framework.agents.utils.litellm.acompletion')
    async def test_llm_fixing_with_retries(self, mock_litellm):
        """Test LLM fixing with retry and context building."""
        # First attempt fails, second succeeds
        responses = [
            # First response - fails
            MagicMock(choices=[MagicMock(message=MagicMock(content='''{
                "rationale": "First attempt failed",
                "fixed_json": "{still_broken: invalid}"
            }'''))]),
            # Second response - succeeds
            MagicMock(choices=[MagicMock(message=MagicMock(content='''{
                "rationale": "Second attempt learned from failure",
                "fixed_json": "{\\"name\\": \\"retry_success\\", \\"value\\": 777, \\"active\\": false}"
            }'''))])
        ]
        mock_litellm.side_effect = responses
        
        malformed_json = 'Invalid format - name=broken, value=777, active=false'
        
        result = await self.parser.parse(malformed_json, TestModel, use_llm_fixing=True)
        
        assert result is not None
        assert result.name == "retry_success"
        assert result.value == 777
        assert result.active is False
        assert mock_litellm.call_count == 2

    def test_prompt_building_without_context(self):
        """Test user prompt building without previous attempts."""
        prompt = self.parser._build_user_prompt(
            malformed_text='{"broken": "json"}',
            original_error="Parsing failed",
            response_model=TestModel,
            previous_attempts=[],
            attempt_number=1
        )
        
        assert "TestModel" in prompt
        assert "Parsing failed" in prompt
        assert '{"broken": "json"}' in prompt
        assert "PREVIOUS FAILED ATTEMPTS" not in prompt

    def test_prompt_building_with_context(self):
        """Test user prompt building with previous failed attempts."""
        previous_attempt = FixingAttempt(
            attempt_number=1,
            malformed_input="broken",
            llm_response=JsonFixingResponse(
                rationale="Tried to fix quotes",
                fixed_json='{"still": "broken"}'
            ),
            error_message="Still failed to parse"
        )
        
        prompt = self.parser._build_user_prompt(
            malformed_text='{"broken": "json"}',
            original_error="Parsing failed",
            response_model=TestModel,
            previous_attempts=[previous_attempt],
            attempt_number=2
        )
        
        assert "PREVIOUS FAILED ATTEMPTS" in prompt
        assert "Tried to fix quotes" in prompt or "No rationale provided" in prompt  # Allow both cases
        assert '{"still": "broken"}' in prompt
        assert "Still failed to parse" in prompt


class TestJsonFixingResponse:
    """Test JsonFixingResponse Pydantic model."""

    def test_valid_response(self):
        """Test creating valid JsonFixingResponse."""
        response = JsonFixingResponse(
            rationale="Fixed missing quotes",
            fixed_json='{"key": "value"}'
        )
        
        assert response.rationale == "Fixed missing quotes"
        assert response.fixed_json == '{"key": "value"}'

    def test_response_from_json(self):
        """Test creating JsonFixingResponse from JSON string."""
        json_data = '''{
            "rationale": "Fixed trailing comma",
            "fixed_json": "{\\"name\\": \\"test\\"}"
        }'''
        
        response = JsonFixingResponse.model_validate_json(json_data)
        
        assert response.rationale == "Fixed trailing comma"
        assert response.fixed_json == '{"name": "test"}'


class TestFixingAttempt:
    """Test FixingAttempt dataclass."""

    def test_fixing_attempt_creation(self):
        """Test creating FixingAttempt instance."""
        llm_response = JsonFixingResponse(
            rationale="Test rationale",
            fixed_json='{"test": true}'
        )
        
        attempt = FixingAttempt(
            attempt_number=1,
            malformed_input="broken json",
            llm_response=llm_response,
            error_message="Test error",
            success=True,
            rationale="Test rationale"
        )
        
        assert attempt.attempt_number == 1
        assert attempt.malformed_input == "broken json"
        assert attempt.llm_response == llm_response
        assert attempt.error_message == "Test error"
        assert attempt.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])