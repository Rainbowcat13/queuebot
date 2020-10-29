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
                      update: Dict = None, delete=False):
        """
        Searches, updates or deletes ONE document by given parameters
        :param collection_name: Name of needed collection
        :param parameters: Fields for search
        :param update: Fields for update (if needed)
        :param delete: Flag for deleting document found
        :return: Nothing if it is update; Document found if it is search or delete
        """
        collection = self[collection_name]
        if update is not None:
            collection.find_one_and_update(parameters, {'$set': update})
            return
        if delete:
            collection.delete_one(parameters)
        return collection.find_one(parameters)

    def aggregate_many(self, collection_name: str, parameters: Dict = None,
                       update: Dict = None, delete=False):
        """
        Searches, updates or deletes ALL documents by given parameters
        :param collection_name: Name of needed collection
        :param parameters: Fields for search
        :param update: Fields for update (if needed)
        :param delete: Flag for deleting documents found
        :return: Nothing if it is update; All documents found if it is search or delete
        """
        if parameters is None:
            parameters = {}
        collection = self[collection_name]
        if update is not None:
            for item in collection.find(parameters):
                collection.find_one_and_update(item, update)
            return
        if delete:
            collection.delete_many(parameters)
        return collection.find(parameters)

    def add_one(self, collection_name: str, fields: Dict):
        """
        Adds one new document to the collection
        :param collection_name: Name of needed collection
        :param fields: fields of the document
        :return: Nothing
        """
        if self.aggregate_one(collection_name, fields) is None:
            self[collection_name].insert_one(fields)

    def add_many(self, collection_name: str, params: Dict[str, List]):
        """
        Adds many new documents to collection
        :param collection_name: Name of needed collection
        :param params: It is a set of keys and by each key you can get
                       a list of values. So this method inserts to collection count=len(params[<any_key>]) elements,
                       each is a dict of all keys from params and values by all keys by index from 0 to count.
        :return: Nothing
        """
        size = 0
        for key, value in params.items():
            size = len(value)
            break
        if size == 0:
            return
        for i in range(size):
            self.add_one(collection_name, {key: value[i] for key, value in params.items()})

    def get_all(self, collection_name):
        """
        Gets all documents from collection
        :param collection_name: Name of needed collection
        :return: All documents from collection
        """
        return self[collection_name].find()

    def __getitem__(self, collection_name):
        """
        Just gets collection by name
        :param collection_name: Name of needed collection
        :return: Collection by collecion_name
        """
        if collection_name in self.collections:
            return self.collections[collection_name]
