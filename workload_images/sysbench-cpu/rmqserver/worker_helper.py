import codecs
import json


def to_json(python_object):
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')


def from_json(json_object):
    if '__class__' in json_object and json_object['__class__'] == 'bytes':
        return codecs.decode(json_object['__value__'].encode(), 'base64')
    return json_object


def encode_base_64(byte_object):
    return str(codecs.encode(byte_object, 'base64').decode("ascii"))


def decode_base_64(b64_object):
    return bytearray(codecs.decode(bytearray(b64_object.encode("ascii")), 'base64'))


def convert_to_json(object):
    return json.dumps(object, default=to_json)


def load_from_json(json_str):
    return json.loads(json_str, object_hook=from_json)
