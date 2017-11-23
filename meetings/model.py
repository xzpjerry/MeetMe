import arrow
from enum import Enum
from math import ceil


class event_compare_result(Enum):
    within = 0
    without = 1


class calendar_event(object):

    def __init__(self, start, end):
        self.flag = False
        self.start = arrow.get(start).to('local')
        self.start_time = arrow.get(self.start.format("HH:mm:ss"), "HH:mm:ss")

        self.end = arrow.get(end).to('local')
        self.end_time = arrow.get(self.end.format("HH:mm:ss"), "HH:mm:ss")

        self.start_timestamp = self.start.timestamp
        self.end_timestamp = self.end.timestamp

        self.duration = (self.end - self.start).total_seconds()
        self.time_duration = (self.end_time - self.start_time).total_seconds()

        if self.duration >= 86400:
            self.flag = True
        if self.time_duration < 0:  # prepare for time range setting like 23:00 ~ 1:00
            self.end_time = self.end_time.shift(days=1)
            self.time_duration = (
                self.end_time - self.start_time).total_seconds()

    def __str__(self):
        result = "(Start: %s    " % self.start
        result += "End: %s    " % self.end
        result += "Duration: %ss, from %s to %s    );" % (
            self.duration, self.start_time.format("HH:mm:ss"), self.end_time.format("HH:mm:ss"))
        return result

    def compare_to(self, eventB):
        if eventB.start >= self.end:
            return event_compare_result.without

        if self.flag:  # self has more than 1 day, it must be on our range
            return event_compare_result.within  # self is within eventB

        if self.start_time >= eventB.end_time or eventB.start_time >= self.end_time:
            return event_compare_result.without  # self is without range

        return event_compare_result.within


class eventrange(calendar_event):

    def __init__(self, start, end, meet_duration=30):
        super(eventrange, self).__init__(start, end)
        self.blockage = []
        self.meet_duration = meet_duration * 60

    def __str__(self):
        result = super(eventrange, self).__str__()
        result += "Blockage in Range: "
        if self.blockage:
            for block in self.blockage:
                result += " "
                result += str(block)
            result += "\nFree time:"
            if self.free:
                for freetime in self.free:
                    result += str(arrow.get(freetime[0]).to('local'))
                    result += " ~ "
                    result += str(arrow.get(freetime[1]).to('local'))
                    result += " ; "
            else:
                result += "None."
        else:
            result += "None and therefore whole range is yours!"
        return result

    def subtract_blockage(self):  # for range instance only

        if self.blockage:
            accurate_subranges = {}

            days = ceil(self.duration / 86400)
            for day in range(days + 1):
                thisdays_start = self.start_timestamp + day * 86400
                thisdays_end = thisdays_start + int(self.time_duration)
                for i in range(thisdays_start, thisdays_end + 1):
                    accurate_subranges[i] = True

            for block in self.blockage:
                for i in range(block.start_timestamp, block.end_timestamp + 1):
                    if accurate_subranges.get(i):
                        accurate_subranges[i] = False

            if accurate_subranges[self.start_timestamp]:
                last_free_start = self.start_timestamp
            else:
                last_free_start = None

            self.free = []
            day_counter = 0
            for i in accurate_subranges:
                if last_free_start and accurate_subranges[i] == False:
                    if (i - last_free_start) >= self.meet_duration:
                        self.free.append((last_free_start, i))
                    last_free_start = None
                elif (last_free_start == None) and accurate_subranges[i]:
                    last_free_start = i
                if day_counter == self.time_duration: # last second
                    if last_free_start and (i - last_free_start) >= self.meet_duration:
                        self.free.append((last_free_start, i))
                day_counter += 1

# DB part
import pymongo
from pymongo import MongoClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from random import randint
import sys
import logging

class DB_config:

    def __init__(self, user, userpw, dbhost, dbport, dbname, db_collection_name = "You_forgot_to_set_collection"):
        self.url = "mongodb://%s:%s@%s:%s/%s" % (
            user, userpw, dbhost, dbport, dbname)
        self.user = user
        self.userpw = userpw
        self.dbhost = dbhost
        self.dbport = dbport
        self.dbname = dbname
        self.db_collection_name = db_collection_name


class record:

    def __init__(self, start = None, end = None, adict = None, duration = 30): # Inputed date will always be in unix timestamp format
        if start != None and end != None:
            self.start = start
            self.end = end
        elif adict != None:
            self.start = adict["start"]
            self.end = adict["end"]
        self.duration = duration
    def formatted(self):
        temp = {"type": "calendar_event",
                "start": self.start,
                "end": self.end,
                "duration": self.duration
                }
        return temp

    def __str__(self):
        return str(self.formatted())


class DB:

    def __init__(self, config : DB_config):
        try:
            self.db = getattr(MongoClient(config.url), config.dbname)
            self.collection = getattr(self.db, config.db_collection_name)
        except:
            logging.warning(
                "Can not connect to the Database, please check your config.")
            sys.exit(1)
        finally:
            logging.info("Now the collection is set.")
            for index in self.collection.list_indexes():
                logging.info("Using index: " + str(index))

    def all_user_collection(self):
        rslt = []
        for collection in self.db.collection_names():
            if "MeetingUser_" in collection:
                rslt.append(collection)
        return rslt

    def rename_collection(self, new_name):
        if type(new_name) == str:
            try:
                self.collection.rename(new_name)
                self.collection = getattr(self.db, new_name)
            except:
                logging.warning("Failed to rename collection.")
                return False
            logging.info("Collection is renamed.")
            return True
        return False

    def collection_name_gen(self):
        base = "MeetingUser_"
        while True:
            attempt = base + str(randint(0, 9999))
            yield attempt

    def set_collection(self, collection):
        try:
            self.collection = getattr(self.db, collection)
        except:
            logging.warning(
                "Can not connect to the collection or the collection is not existed? Do you have permission to write?.")
            raise
        finally:
            logging.info("Now the collection is set.")
            for index in self.collection.list_indexes():
                logging.info("Using index: " + str(index))

    def del_collection(self):
        if self.collection != None:
            try:
                self.collection.drop()
            except Exception as e:
                logging.warning("Deletion of a collection failed.")
                raise
            finally:
                logging.info("A collection deleted.")

    def insert(self, new_record):
        if self.collection != None:
            try:
                logging.info("Inserting " + str(new_record))
                self.collection.insert(new_record.formatted())
            except:
                logging.warning(
                    "Can not connect to the collection, is the collection exist? Do you have permission to write?.")
                logging.warning("Insertion failed.")
                raise
            finally:
                logging.info("Record inserted.")
        else:
            logging.warning("Collection is not yet set.")
            logging.warning("Insertion failed.")

    def del_record(self, record):
        try:
            self.collection.delete_many(record.formatted())
        except:
            logging.warning("Failed to delete a record.")
            raise
        finally:
            logging.info("A record deleted.")

    def get_all(self):
        if self.collection != None:
            try:
                records = []
                for onerecord in self.collection.find():
                    del onerecord['_id']
                    records.append(onerecord)
            except:
                logging.warning(
                    "Can not connect to the collection, is the collection exist? Do you have permission to write?.")
                logging.warning("Fetch failed.")
                raise
            finally:
                return records
        else:
            logging.warning("Collection is not yet set.")
            logging.warning("Finding failed.")
