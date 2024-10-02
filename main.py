import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.chains import LLMChain
from langchain.schema import  HumanMessage, AIMessage
from langchain.prompts import PromptTemplate
import requests
# Load environment variables

load_dotenv()
app = Flask(__name__)

BACKEND_API_ENDPOINT = "http://localhost:3000/chats/session/"

# Load the Groq API key
os.environ['GROQ_API_KEY'] = "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"

llm = ChatGroq(model_name="llama-3.1-70b-versatile")
# llm = ChatGroq(model_name="llama-3.1-8b-instant")

# Define a simple prompt template for the conversation
prompt_template = PromptTemplate(
    input_variables=["user_input", "history"],
    template="You are a helpful assistant. Respond to the user's question: {user_input} and Previous conversation: {history}"
)

conversation_chain = LLMChain(
    llm=llm,
    prompt=prompt_template,
)

# Helper functions

def generate_topic_description(algorithm):
    prompt = f"You are a Informative Assistance for data structure topic. Please give the details Introduction of {algorithm}."
    response = llm.invoke(prompt)
    return response.content

def generate_question(algorithm):
    prompt = f"You are a teaching assistant for data structure. The student is learning {algorithm}. Generate a Socratic question that is appropriate to their current understanding."
    response = llm.invoke(prompt)
    return response.content

def socratic_followup(question, user_answer):
    prompt = f"The question was: '{question}'. The student answered: '{user_answer}'. If the answer was wrong, generate a simpler, guiding question. If it was correct, generate the next more complex question."
    response = llm.invoke(prompt)
    return response.content

def custom_question_response(user_question, memory):
    que = f"Answer the following question: '{user_question}'"
    if memory:
        response = conversation_chain.invoke({"user_input": que, "history": memory})
    else:
        response = conversation_chain.invoke({"user_input": que, "history": ""})
    return response['text']

db_req = {
    "userId" : "",
    "sessionId": "",
    "userPrompt": "",
    "aiResponse": ""
}

USERID = 'userId'
SESSIONID = 'sessionId'
TOPIC_NAME = 'topicName'
CHAT_TYPE = 'chatType'
USER_PROMPT = 'userPrompt'
HISTORY = 'history'
AI_RESPONSE = 'aiResponse'

def generate_object_list(memory_db_list):
    memory = []
    for i in range(len(memory_db_list)):
        memory.append(HumanMessage(content=memory_db_list[i]['user']))
        memory.append(AIMessage(content=memory_db_list[i]['ai']))
    return memory

# API route for handling conversation
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    if data[USERID] and data[SESSIONID] and data[TOPIC_NAME] and data[CHAT_TYPE]:
        db_req[USERID] = data[USERID]
        db_req[SESSIONID] = data[SESSIONID]
        db_req[USER_PROMPT] = data[USER_PROMPT]

        chat_type = data.get(CHAT_TYPE)
        selected_topic = data.get(TOPIC_NAME)
        user_question = data.get(USER_PROMPT)
        history_list = data.get(HISTORY)
        memory_object = generate_object_list(history_list)

        if chat_type == "question":
            if user_question:
                response = custom_question_response(user_question, memory_object)
                db_req[AI_RESPONSE] = response
                try:
                    post_response = requests.post(BACKEND_API_ENDPOINT + db_req['sessionId'], json=db_req)
                    post_response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(e)
                    return jsonify({"error": "Error calling the external API"}), 500
                return jsonify({"aiResponse": response})
            else:
                return jsonify({"error": "Please provide a question."}), 400            

        elif chat_type == "learn" and user_question.strip() == "":
            # print("Entering the learn with zero answer")
            response = generate_topic_description(selected_topic)
            first_question = generate_question(selected_topic)
            db_req[AI_RESPONSE] = response
            
            try:
                post_response = requests.post(BACKEND_API_ENDPOINT + db_req['sessionId'], json=db_req)
                post_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(e)
                return jsonify({"error": "Error calling the external API"}), 500
            db_req[AI_RESPONSE] = first_question

            try:
                post_response = requests.post(BACKEND_API_ENDPOINT + db_req['sessionId'], json=db_req)
                post_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(e)
                return jsonify({"error": "Error calling the external API"}), 500
            return jsonify({"aiResponse": response, "aiQuestion": first_question})
        elif chat_type == "learn" and user_question:
            # print("Entering the question with follow up question")
            last_question = history_list[len(history_list)-1]['ai']
            follow_up = socratic_followup(last_question, user_question)
            db_req[AI_RESPONSE] = follow_up
            try:
                post_response = requests.post(BACKEND_API_ENDPOINT + db_req['sessionId'], json=db_req)
                post_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(e)
                return jsonify({"error": "Error calling the external API"}), 500
            return jsonify({"question": follow_up})
    return jsonify({"error": "Invalid request"}), 400

if __name__ == '__main__':
    app.run(debug=True)