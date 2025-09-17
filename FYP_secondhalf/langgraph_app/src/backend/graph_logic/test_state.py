import os
import asyncio
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv(override=True)

async def test_llm_connection():
    """Test LLM connection with various scenarios"""
    
    print("=== LLM Connection Test ===")
    
    # Step 1: Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: No OpenAI API key found in environment variables")
        print("Please set OPENAI_API_KEY in your .env file or environment")
        return
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    
    try:
        # Step 2: Initialize LLM
        print("\n--- Initializing LLM ---")
        llm = init_chat_model("openai:gpt-4.1")
        print("✅ LLM initialized successfully")
        
        # Step 3: Simple test
        print("\n--- Testing Simple API Call ---")
        simple_response = await llm.ainvoke([
            HumanMessage(content="Hello, are you working? Please respond with just 'Yes, I am working.'")
        ])
        print(f"✅ Simple LLM test successful: {simple_response.content}")
        
        # Step 4: Test with system message
        print("\n--- Testing with System Message ---")
        system_response = await llm.ainvoke([
            SystemMessage(content="You are a helpful assistant. Respond briefly."),
            HumanMessage(content="What is 2+2?")
        ])
        print(f"✅ System message test successful: {system_response.content}")
        
        # Step 5: Test with longer content (similar to your use case)
        print("\n--- Testing with Longer Content ---")
        long_content = """
        • ID: R1
        ○ Name: Food Diary Feature
        ○ Description: Implement a food diary that allows users to log their meals, track dietary habits, and receive personalized insights.
        ○ Priority: High
        • ID: R2
        ○ Name: Personalized Recommendations  
        ○ Description: Utilize machine learning algorithms to provide users with personalized meal recommendations.
        ○ Priority: High
        """
        
        long_response = await llm.ainvoke([
            SystemMessage(content="Analyze the following requirements and provide a brief summary."),
            HumanMessage(content=long_content)
        ])
        print(f"✅ Long content test successful: {long_response.content[:100]}...")
        
        # Step 6: Test with timeout
        print("\n--- Testing with Timeout ---")
        try:
            timeout_response = await asyncio.wait_for(
                llm.ainvoke([HumanMessage(content="Count from 1 to 5.")]),
                timeout=30.0
            )
            print(f"✅ Timeout test successful: {timeout_response.content}")
        except asyncio.TimeoutError:
            print("❌ LLM call timed out after 30 seconds")
        
        print("\n🎉 All LLM tests passed successfully!")
        
    except Exception as e:
        print(f"❌ LLM test failed: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        
        # Additional debugging info
        if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
            print("\n💡 Tip: This looks like an API key issue. Check your OpenAI API key.")
        elif "rate limit" in str(e).lower():
            print("\n💡 Tip: You may have hit OpenAI's rate limit. Wait a moment and try again.")
        elif "quota" in str(e).lower() or "billing" in str(e).lower():
            print("\n💡 Tip: This looks like a billing/quota issue. Check your OpenAI account billing.")
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            print("\n💡 Tip: This looks like a network connectivity issue.")
        
        import traceback
        print(f"\nFull traceback:\n{traceback.format_exc()}")

def main():
    """Main function to run the test"""
    try:
        asyncio.run(test_llm_connection())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()