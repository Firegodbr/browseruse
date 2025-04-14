import os, time
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller,BrowserConfig, Browser
from dotenv import load_dotenv
from fastapi import FastAPI

# Initialize FastAPI app
app = FastAPI()
load_dotenv()
config = BrowserConfig(
    # headless=True,
    headless=False,
    disable_security=False
)

browser = Browser(config=config)
controller = Controller()
async def scrape_website(search):
    # start_time = time.time()
    task = f"""
    1 - Search base on the {search} and press "Enter" to search.
    If there's a list of elements on the screen:
        Give me the list of elements that show up and finish the operation
    else
        Give me all the information about his vehicle if there's more than one give information for all of them
    """
    # Pass the sensitive data to the agent
    initial_actions = [
	{'go_to_url': {'url': 'https://toyosteu.sdswebapp.com:6819/SDSWeb/t6/appointments-qab/2'}},
	{'input_text': {'index': 4, 'text': os.getenv('USERNAME_SDS')}, "has_sensitive_data": True},
	{'input_text': {'index': 7, 'text': os.getenv('PASSWORD_SDS')}, "has_sensitive_data": True},
	{'click_element': {'index': 11}},
	{'click_element': {'index': 12}},
	{'click_element': {'index': 7}},
    ]
    
        # agent = Agent(task=task, llm=ChatOpenAI(model="gpt-4o"),initial_actions=initial_actions, sensitive_data=sensitive_data)
    agent = Agent(task=task, llm=ChatOpenAI(model="gpt-4o"),initial_actions=initial_actions,browser=browser)
    history =  await agent.run()
    result = history.final_result()
    extracted = history.extracted_content()
    agent.browser.close()
    # end_time  = time.time()
    # execution_time = end_time - start_time
    # print(f"Execution time: {execution_time} seconds")
    if result:
        return result
    else:
        return extracted[len(extracted)-1]
        

# Define FastAPI route
@app.get("/")
def scrape_api():
    """
    API endpoint to welcome.
    Example: GET http://127.0.0.1:8000/scrape?search_string=https://example.com
    """
    return {"page_title": "hello"}
@app.get("/scrape")
async def scrape_api(search_string: str):
    """
    API endpoint to scrape a webpage's title.
    Example: GET http://127.0.0.1:8000/scrape?search_string=https://example.com
    """
    result = await scrape_website(search_string)
    return {"page_title": result}
# asyncio.run(scrape_website("number 450-475-7653"))
# asyncio.run(main("nom Andre Tremblay"))