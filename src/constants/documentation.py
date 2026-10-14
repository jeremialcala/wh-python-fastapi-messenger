# -*- coding: utf-8 -*-

TITLE = "Facebook Messenger Webhook Manager"

SUMMARY = "Controls the Facebook Messenger Lifecycle"

TERMS = "https://web-ones.com/terms"

DESCRIPTION = """
This is a Webhook for Facebook Messenger chatbot, 
this application manages the chatbot lifecycle for messenger and creates events 
to respond to and from Facebook. 

### BOT 

* /bot: This endpoint controls the chatbot lifecycle, will have the fallowing operations:
    * @POST: Create a new chatbot requiring simple data and returning and UUID
    * @GET: Will obtain the chatbot information using the param _id={BOT-ID}
    
* /chat: This webhook controls the chat lifecycle for an specific bot, will have the following operations:
    * @GET: using the param bot_id={BOT-ID} (required) will do Facebook token verification challenge
    * @POST: using the param bot_id={BOT-ID} (required) will process a message send from Facebook to be processed by this instance

* /chat/{BOT-ID}/phones: This operation manage the Whatsapp Phone Numbers
    * @POST: Add a whatsapp phone number to your bot.
    * @GET: This operation Obtains all Phones associated to this bot. With the param ?phone.id={phone_id} will give you a specific number.  
"""

TAGS_METADATA = [
    {
        "name": "Clients",
        "description": "The registry of clients and of the public keys they sign their tokens with."
    },
    {
        "name": "Bot",
        "description": "This entry will manage the chatbot lifecycle, ",
    },
    {
        "name": "Chat",
        "description": "This is conversation management and communication control"
    },
    {
        "name": "Contacts",
        "description": "The people who wrote to a chatbot: listing them, finding one, exporting what is stored "
                       "about it and deleting it."
    },
    {
        "name": "Intents",
        "description": "Configure intents and their actions (API calls) as LLM tool definitions, "
                       "stored per chatbot and consumed by the downstream worker."
    }
]

CONTACT = {
      "name": "Jeremi Alcala",
      "url": "https://jeremi.web-ones.com",
      "email": "jeremialcala@gmail.com",
    }

