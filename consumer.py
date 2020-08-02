from json import JSONDecodeError
import nsq
from app import get_word_count
from marshmallow import Schema, fields


class MessageSchema(Schema):
    address = fields.Str()
    id = fields.Str()


def handler(message):
    schema = MessageSchema()
    try:
        result = schema.loads(message.body.decode())
        get_word_count.delay(result['id'], result['address'])
        return True
    except JSONDecodeError:
        return False


r = nsq.Reader(message_handler=handler, nsqd_tcp_addresses=['nsqd:4150'], topic="parsed_data", channel="parse",
               lookupd_poll_interval=15)

if __name__ == '__main__':
    nsq.run()
