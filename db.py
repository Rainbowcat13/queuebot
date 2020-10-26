import pymongo
from pymongo.collection import Collection
from typing import Dict


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

    def aggregate_one(self, collection_name, parameters, update=None, delete=False):
        collection = self[collection_name]
        if update is not None:
            return collection.find_one_and_update(parameters, {'$set': update})
        result = collection.find_one(parameters)
        if delete is not None:
            collection.delete_one(parameters)
        return result

    def aggregate_many(self, collection_name, parameters=None, update=None, delete=False):
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

    def add_one(self, collection_name, fields):
        self[collection_name].insert_one(fields)

    def __getitem__(self, collection_name):
        if collection_name in self.collections:
            return self.collections['collection_name']
