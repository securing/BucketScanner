#!/bin/env python
'''
--------------
BucketScanner
By @Rzepsky
Updated by @_pkusik
--------------
======================= Notes =======================
This tool is made for legal purpose only!!! It allows you to:
- find collectable files for an anonymous/authenticated user in your buckets
- verify if an anonymous/authenticated user is allowed to upload arbitrary files to your buckets


====================== Options ======================
-l: specify a list with bucket names to check.
-w: specify a file to upload to a bucket.
-r: specify a regular expression to filter the output.
-s: look only for files bigger than 's' bytes 
-m: look only for files smaller than 'm' bytes 
-t: specify number of threads to use.
-o: specify an output file.
-p: specify a AWS profile name.
-pm: passive mode which only checks readibility of the bucket (can be combined with write test).
-d: detailed mode (more output files with details if the bucket exists, if listable, objects are downloadable and if writable) (works only with passive mode and/or write test).
-h: prints a help message.

====================== Example ======================

$ python BucketScanner.py -l bucket_list.txt -w upload_file.txt -r '^.*\.(db|sql)' -t 50 -m 5242880 -o output.txt


The above command will:
- test all buckets from bucket_list.txt file
- test if you can upload upload_file.txt to any of the bucket included in bucket_list.txt
- provide URLs in output.txt only to files bigger than 5 MB and with .db or .sql extension
- work on 50 threads
'''

from argparse import ArgumentParser
from threading import Thread, Lock
from botocore.exceptions import ProfileNotFound
from botocore import UNSIGNED
from botocore.client import Config
from termcolor import colored
import math
import boto3
import requests
import queue
import re
import sys


queue = queue.Queue()


class Settings(object):

    def __init__(self):
        self._WRITE_TEST_ENABLED = False
        self._WRITE_TEST_FILE = False
        self._OUTPUT_FILE = "output.txt"
        self._NOTACCESIBLE_FILE = "notaccesible.txt"
        self._NONEXISTING_FILE = "nonexisting.txt"
        self._NONDOWNLOADABLE_FILE = "nondownloadable.txt"
        self._NONWRITABLE_FILE = "nonwritable.txt"
        self._WRITABLE_FILE = "writable.txt"
        self._DOWNLOADABLE_FILE = "downloadable.txt"
        self._LISTABLE_FILE = "listable.txt"
        self._MIN_SIZE = 1
        self._MAX_SIZE = 0
        self._REGEX = ".*"
        self._ANONYMOUS_MODE = False
        self._DISPLAY_SIZE = True
        self._PROFILE_NAME = 'default'
        self._PASSIVE_MODE = False
        self._DETAILED_MODE = False

    def set_write_test(self, write_file):
        self._WRITE_TEST_ENABLED = True
        self._WRITE_TEST_FILE = write_file

    def set_output_file(self, output_file):
        self._OUTPUT_FILE = output_file

    def set_minsize(self, min_SIZE):
        self._MIN_SIZE = min_SIZE

    def set_maxsize(self, max_SIZE):
        self._MAX_SIZE = max_SIZE

    def set_anonymous_mode(self):
        self._ANONYMOUS_MODE = True
        print(colored('''All tests will be executed in anonymous mode:
        If you want to send all requests using your AWS account please use -p [profile_name] argument
        ''', 'magenta'))

    def set_regex(self, regex):
        self._REGEX = regex

    def set_profile(self, profile):
        self._PROFILE_NAME = profile
        if not self.test_profile():
            self.set_anonymous_mode()

    def test_profile(self):
        try:
            boto3.Session(profile_name=self._PROFILE_NAME)
        except ProfileNotFound:
            print(colored(f"Profile {self._PROFILE_NAME} not found", 'red'))
            return False
        return True

    def set_passive_mode(self):
        self._PASSIVE_MODE = True

    def set_detailed_mode(self):
        self._DETAILED_MODE = True


def get_region(bucket_name):
    try:
        response = requests.get('http://' + bucket_name + '.s3.amazonaws.com/')
        region = response.headers.get('x-amz-bucket-region')
        return region
    except Exception as e:
        print(colored(f"Error: couldn't connect to '{response}' bucket. Details: {e}", 'red'))


def get_session(bucket_name, region):
    try:
        if settings._ANONYMOUS_MODE:
            sess = boto3.Session(region_name=region)
            conn = sess.resource('s3', config=Config(signature_version=UNSIGNED))
        else:
            sess = boto3.Session(
                profile_name=settings._PROFILE_NAME,
                region_name=region
            )
            conn = sess.resource('s3')
        bucket = conn.Bucket(bucket_name)
        return bucket

    except Exception as e:
        print(colored(f"Error: couldn't create a session with '{bucket_name}' bucket. Details: {e}", 'red'))


def get_bucket(bucket_name):
    region = get_region(bucket_name)
    bucket = ""
    if region is None:
        print(colored(f"Bucket '{bucket_name}' does not exist.", 'magenta'))
        if settings._DETAILED_MODE:
            append_output(bucket_name + "\n", settings._NONEXISTING_FILE)
    else:
        bucket = get_session(bucket_name, region)
    return bucket


def size(size_bytes):
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "{0}{1}".format(s, size_name[i])


def is_in_limits(minsize, maxsize, content_length):
    if maxsize:
        return minsize < content_length < maxsize
    return minsize < content_length


def bucket_reader(bucket_name):
    region = get_region(bucket_name)
    if region is None:
        print(colored(f"Bucket '{bucket_name}' does not exist", 'magenta'))
        if settings._DETAILED_MODE:
            append_output(bucket_name + "\n", settings._NONEXISTING_FILE)
        pass
    else:
        print(f"Testing bucket '{bucket_name}'...")
        bucket = get_bucket(bucket_name)
        try:
            if settings._PASSIVE_MODE:
                results, downloadable = passive_reader(bucket, bucket_name)
            else:
                results = active_reader(bucket, bucket_name)

            if settings._DETAILED_MODE:
                append_output(results + "\n", settings._LISTABLE_FILE)
                append_output(downloadable + "\n", settings._DOWNLOADABLE_FILE)
            else:
                append_output(results, settings._OUTPUT_FILE)
        except Exception as e:
            print(colored(f"Error: couldn't access the '{bucket_name}' bucket. Details: {e}", 'yellow'))
            if settings._DETAILED_MODE:
                append_output(bucket_name + "\n", settings._NOTACCESIBLE_FILE)


def passive_reader(bucket, bucket_name):
    listable = ""
    downloadable = ""
    first_check = True
    for s3_object in bucket.objects.all():
        try:
            if s3_object.key:
                if first_check:
                    print(colored(f"{bucket_name} is listable!", 'green'))
                    listable += bucket_name + '\n'
                    first_check = False
                s3_object.get()
                downloadable += bucket_name + '\n'
                print(colored(f"{bucket_name} is possible to download!!", 'green'))
                break
        except Exception as e:
            print(colored(f"Error: couldn't get '{s3_object.key}' object in '{bucket_name}' bucket. Details: {e}", 'yellow'))
            if settings._DETAILED_MODE:
                append_output(bucket_name + "\n", settings._NONDOWNLOADABLE_FILE)
            break
    return listable, downloadable


def active_reader(bucket, bucket_name):
    results = ""
    for s3_object in bucket.objects.all():
        try:
            content_length = s3_object.get()["ContentLength"]
            if is_in_limits(settings._MIN_SIZE, settings._MAX_SIZE, content_length) and \
                    re.match(settings._REGEX, s3_object.key):

                item = "http://s3.{0}.amazonaws.com/{1}/{2}".format(
                    region, bucket_name,
                    s3_object.key)
                results += item + '\n'
                print(f"Collectable: {item} {size(content_length)}")
        except Exception as e:
            print(colored(f"Error: couldn't get '{s3_object.key}' object in '{bucket_name}' bucket. Details: {e}", 'yellow'))
    return results


def write_test(bucket_name, filename):
    region = get_region(bucket_name)
    if region != 'None':
        try:
            data = open(filename, 'rb')
            bucket = get_bucket(bucket_name)
            if bucket == "":
                return
            bucket.put_object(Bucket=bucket_name, Key=filename, Body=data)
            print(colored(f"Success: bucket '{bucket_name.encode('utf-8')}' allows for uploading arbitrary files!!!", 'green'))
            results = "http://s3.{0}.amazonaws.com/{1}/{2}\n".format(region,
                                                                     bucket_name,
                                                                     filename)
            append_output(results, settings._OUTPUT_FILE)
            if settings._DETAILED_MODE:
                append_output(bucket_name + "\n", settings._WRITABLE_FILE)
        except Exception as e:
            print(colored(f"Error: couldn't upload a {filename} file to {bucket_name}. Details: {e}\n", 'yellow'))
            if settings._DETAILED_MODE:
                append_output(bucket_name + "\n", settings._NONWRITABLE_FILE)


def append_output(results, file):
    with open(file, "a") as output:
        output.write(results)


def bucket_worker():
    while True:
        try:
            bucket = queue.get()
            bucket_reader(bucket)
            if settings._WRITE_TEST_ENABLED:
                write_test(bucket, settings._WRITE_TEST_FILE)
        except Exception as e:
            print(colored(f"Error: {e}\n", 'red'))
        queue.task_done()


def print_help():
    print('''
--------------
BucketScanner
By @Rzepsky
Updated by @_pkusik
--------------
======================= Notes =======================
This tool is made for legal purpose only!!! It allows you to:
- find collectable files for an anonymous/authenticated user in your buckets
- verify if an anonymous/authenticated user is allowed to upload arbitrary files to your buckets


====================== Options ======================
-l: specify a list with bucket names to check.
-w: specify a file to upload to a bucket.
-r: specify a regular expression to filter the output.
-s: look only for files bigger than 's' bytes
-m: look only for files smaller than 'm' bytes
-t: specify number of threads to use.
-o: specify an output file.
-p: specify a AWS profile name.
-h: prints a help message.
-pm: passive mode which only checks readibility of the bucket (can be combined with write test).
-d: detailed mode (more output files with details if the bucket exists, if listable, objects are downloadable and if writable) (works only with passive mode and/or write test).

====================== Example ======================

$ python BucketScanner.py -l bucket_list.txt -w upload_file.txt -r '^.*\.(db|sql)' -t 50 -m 5242880 -o output.txt


The above command will:
- test all buckets from bucket_list.txt file
- test if you can upload upload_file.txt to any of the bucket included in bucket_list.txt
- provide URLs in output.txt only to files bigger than 5 MB and with .db or .sql extension
- work on 50 threads
''')


def closing_words():
    if settings._DETAILED_MODE:
        print(colored(f"""\nThat's all folks! Sum up of scan can be found in 
            {settings._LISTABLE_FILE}, 
            {settings._DOWNLOADABLE_FILE}, 
            {settings._WRITABLE_FILE} (if tested), 
            {settings._NONWRITABLE_FILE} (if tested), 
            {settings._NONDOWNLOADABLE_FILE}, 
            {settings._NONEXISTING_FILE}, 
            {settings._NOTACCESIBLE_FILE}.""", attrs=['bold']))
    elif settings._PASSIVE_MODE:
        print(colored(f"\nThat's all folks! All listable bucket names can be found in {settings._OUTPUT_FILE}.", attrs=['bold']))
    else:
        print(colored(f"\nThat's all folks! All collectable files can be found in {settings._OUTPUT_FILE}.", attrs=['bold']))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-l", dest="bucket_list", required=True, help="a list with bucket names.")
    parser.add_argument("-w", dest="write", type=str, required=False,
                        default="", help="file to execute upload test.")
    parser.add_argument("-r", dest="regex", required=False,
                        default='', help="regular expression filter")
    parser.add_argument("-s", dest="min", type=int, required=False, default=1, help="minimum size.")
    parser.add_argument("-m", dest="max", type=int, required=False, default=0, help="maximum size.")
    parser.add_argument("-t", dest="threads", type=int, required=False,
                        default=10, help="thread count.")
    parser.add_argument("-o", dest="output", type=str, required=False,
                        default="output.txt", help="output file.")
    parser.add_argument("-p", dest="profile", type=str, required=False,
                        default="default", help="AWS profile name.")
    parser.add_argument("-pm", dest="passive_mode", required=False, 
                        action="store_true", help="checks readibility of the bucket (can be combined with write test).")
    parser.add_argument("-d", dest="detailed", required=False,
                        action="store_true", help="create detailed output (only with passive and/or write mode).")

    if len(sys.argv) == 1:
        print_help()
        sys.exit()

    settings = Settings()
    arguments = parser.parse_args()

    if arguments.output != "output.txt":
        settings.set_output_file(arguments.output)

    if arguments.write:
        settings.set_write_test(arguments.write)

    if arguments.regex:
        settings.set_regex(arguments.regex)

    if arguments.min > 1:
        settings.set_minsize(arguments.min)

    if arguments.max > 1:
        settings.set_maxsize(arguments.max)

    if arguments.profile:
        settings.set_profile(arguments.profile)
    
    if arguments.passive_mode:
        settings.set_passive_mode()

    if arguments.detailed:
        settings.set_detailed_mode()

    for i in range(0, arguments.threads):
        t = Thread(target=bucket_worker)
        t.daemon = True
        t.start()

    with open(arguments.bucket_list, 'r') as f:
        for bucket in f:
            queue.put(bucket.rstrip())
        queue.join()

    closing_words()
