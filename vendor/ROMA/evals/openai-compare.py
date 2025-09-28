
from openai import OpenAI

client = OpenAI()
client_router = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=...
)

'''response = client.responses.create(
    model="gpt-4o",
    tools=[{ "type": "web_search_preview" }],
    input="What was a positive news story from today?",
)'''

web_search_questions = [
    "What are the current eligibility criteria for the H-1B visa in the United States in 2025?",
    "Who won the Palme d’Or at the 2025 Cannes Film Festival and what was the winning film about?",
    "What is the average salary of a machine learning engineer in Berlin as of mid-2025?",
    "What are the side effects of the latest GLP-1 weight loss drugs approved by the FDA?",
    "Compare the 2025 Tesla Model 3 vs the Hyundai Ioniq 6 in terms of range and charging speed.",
    "What are the major criticisms of OpenAI’s GPT-5 from academic researchers?",
    "How did the Turkish lira perform against the US dollar in Q2 2025?",
    "Which countries were added to the Schengen Area in 2025, if any?",
    "Is there any scientific evidence supporting the use of NMN supplements for longevity as of 2025?",
    "What are the best-reviewed restaurants in Kyoto specializing in kaiseki cuisine this summer?"
]

for question in web_search_questions:
    print("QUESTION:\n\n")
    print("OPENAI:\n\n")    
    response = client.chat.completions.create(
        model="gpt-4o-search-preview",
        messages=[
            {
            "role": "user",
            "content": question
            }
    ]
    )
    print(response.choices[0].message.content)
    print("\n\n\n\n")
    print("OPENROUTER:\n\n")
    completion = client_router.chat.completions.create(
    model="openai/gpt-4o-search-preview",
    messages=[
        {
        "role": "user",
        "content": question
        }
    ]
    )
    print(completion.choices[0].message.content)
    print("\n\n\n\n")

