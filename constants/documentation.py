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

* /answers: This webhook will send the process answer to the chat client using the facebook graph api.
    * @POST: Will send the content of this answer to final user conversation.
"""

TAGS_METADATA = [
    {
        "name": "Bot",
        "description": "This entry will manage the chatbot lifecycle, ",
    },
    {
        "name": "Chat",
        "description": "This is conversation management and communication control"
    }
]

CONTACT = {
      "name": "Jeremi Alcala",
      "url": "https://jeremi.web-ones.com",
      "email": "jeremialcala@gmail.com",
    }

