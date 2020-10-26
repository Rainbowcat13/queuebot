import pymongo
from pymongo.collection import Collection
from typing import Dict, List


class DBConnector:
    MONGO_CLIENT: str = open('config/mongo', 'r').read()

    def __init__(self):
        self.database = pymongo.MongoClient(DBConnector.MONGO_CLIENT)['queue']
        self.collections: Dict[str, Collection] = {
            'users': self.database['users'],
            'students': self.database['students'],
            'homeworks': self.database['homeworks'],
            'admins': self.database['admins'],
            'queues': self.database['queues'],
            'chats_with_broadcast': self.database['chats_with_broadcast']
        }

    def aggregate_one(self, collection_name: str, parameters: Dict,
                      update: Dict=None, delete=False):
        collection = self[collection_name]
        if update is not None:
            return collection.find_one_and_update(parameters, {'$set': update})
        result = collection.find_one(parameters)
        if delete is not None:
            collection.delete_one(parameters)
        return result

    def aggregate_many(self, collection_name: str, parameters: Dict=None,
                       update: Dict=None, delete=False):
        if parameters is None:
            parameters = {}
        collection = self[collection_name]
        if update is not None:
            for item in collection.find(parameters):
                yield collection.find_one_and_update(item, update)
        result = collection.find(parameters)
        if delete:
            collection.delete_many(parameters)
        return result

    def add_one(self, collection_name: str, fields: Dict):
        if self.aggregate_one(collection_name, fields) is None:
            self[collection_name].insert_one(fields)

    def add_many(self, collection_name: str, params: Dict[str, List]):
        """
        :param collection_name: Name of needed collection, it's simple
        :param params: This shit is working like this -- params have a set of keys and by each key you can get
                       a list of values. So this insert to collection count=len(params[<any_key>]) elements,
                       each is a dict of all keys from params and values by all keys by index from 0 to count.
                       Fuck you I can't explain it properly.
        :return: Literally nothing
        """
        size = 0
        for key, value in params:
            size = len(value)
            break
        if size == 0:
            return
        for i in range(size):
            self.add_one(collection_name, {key: value[i] for key, value in params})

    def __getitem__(self, collection_name):
        if collection_name in self.collections:
            return self.collections['collection_name']
