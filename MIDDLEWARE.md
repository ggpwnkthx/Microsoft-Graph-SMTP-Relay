# Middleware support


![Events in MicrosoftGraphHandler](./Resources/flow.svg "Events in MicrosoftGraphHandler")

Microsoft Graph SMTP Relay supports a simple `EventBus` implementation allowing to subscribe to different event names.\
Also, the `MIDDLEWARE_DIR` environments variable defines a location to load additional python modules as middleware (default `app/middleware/*.py`)

### Example of a middleware implementation

Example middleware using the `skip_send` event to skip email submission

```python
# app/middleware/skip_sendmail.py
from event_bus import event_bus_instance
from handlers.microsoft_graph import MicrosoftGraphHandler

class Middleware:
    def __init__(self, msGraphHandler: MicrosoftGraphHandler):
        # ...
        event_bus_instance.subscribe('skip_send', self.skipSendmail)

    def skip_sendmail(self):
        # return True to skip email submission
        return True
```

Another example on how to modify email subject

```python
class Middleware:
    """
    Middleware to demonstrate EmailMessage modifications by adding a prefix to the "Subject" header
    """

    def __init__(self, msGraphHandler: MicrosoftGraphHandler):
        self.app = msGraphHandler.app

        event_bus_instance.subscribe('before_send',self.modify_mail)

    def modify_mail(self, mail_message: EmailMessage):
        subject = mail_message["Subject"]
        logging.info(f"ReplaceSubject -> Adding prefix to subject")
        mail_message.replace_header('Subject', '[ReplaceSubject middleware] ' + subject)
```

### Event subscriptions and EventBus

Below class graph displays methods in the EventBus

![Events in MicrosoftGraphHandler](./Resources/event_bus.svg "Events in MicrosoftGraphHandler")

Example

```python
# subscribe to "sender" event and call my_sender_func when published
from event_bus import event_bus_instance
event_bus_instance.subscribe('sender', self.my_sender_func)
```

### List of Event subscriptions

| Event name         | Arguments                   | Description                                              |
| ------------------ | --------------------------- | -------------------------------------------------------- |
| before_auth        | auth_data                   | before authorization                                     |
| after_auth         | auth_data                   | after authorization                                      |
| before_send        | email_message               | before email submission                                  |
| sender             | mail_from                   | When sender is known                                     |
| recipients         | to, cc, bcc                 | When recipients are known                                |
| skip_send          |                             | Used to skip mail submission (dependent on return value) |
| after_send         |                             | after email submission                                   |
