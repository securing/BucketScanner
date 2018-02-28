#!/bin/env python
'''
--------------
BucketScanner
By @Rzepsky
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
import math
import boto3
import requests
import Queue
import re
import sys

queue = Queue.Queue()

AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''
ANONYMOUS_MODE = False
DISPLAY_SIZE = True
WRITE_TEST_ENABLED = False
WRITE_TEST_FILE = ""
OUTPUT_FILE = "output.txt"
MIN_SIZE = 1
MAX_SIZE = 0
REGEX = ".*"

def setwriteTest(write_file):
    global WRITE_TEST_ENABLED
    global WRITE_TEST_FILE
    WRITE_TEST_ENABLED = True
    WRITE_TEST_FILE = write_file

def setOutputFile(output_file):
    global OUTPUT_FILE
    OUTPUT_FILE = output_file

def setMinsize(min_SIZE):
    global MIN_SIZE
    MIN_SIZE = min_SIZE

def setMaxsize(max_SIZE):
    global MAX_SIZE
    MAX_SIZE = max_SIZE

def setAnonymousMode():
    global ANONYMOUS_MODE
    ANONYMOUS_MODE = True
    print "All tests will be executed in anonymous mode. If you want to send all requests using your AWS account, \
    please specify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY variables in {0} file".format(sys.argv[0])

def setRegex(regex):
    global REGEX
    REGEX = regex

def GetRegion(bucket_name):
        try:
            response = requests.get('http://'+bucket_name+'.s3.amazonaws.com/')
            region = response.headers.get('x-amz-bucket-region')
            return region
        except Exception as e:
            print "Error: couldn't connect to '{0}' bucket. Details: {1}".format(response, e)

def getSession(bucket_name, region):
    try:
        if ANONYMOUS_MODE == True:
            sess = boto3.session.Session(region_name=region)
        else:
            sess = boto3.session.Session(region_name=region, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)    
        conn = sess.resource('s3')
        bucket = conn.Bucket(bucket_name)
        return bucket

    except Exception as e:
        print "Error: couldn't create a session with '{0}' bucket. Details: {1}".format(bucket_name, e)

def getBucket(bucket_name):
    region = GetRegion(bucket_name)
    bucket = ""
    if region == 'None':
        print "Bucket '{0}' does not exist.".format(bucket_name.encode('utf-8'))
    else:
        bucket = getSession(bucket_name, region)
    return bucket

def size(size_bytes):
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "{0}{1}".format(s, size_name[i])

def bucketReader(bucket_name):
    region = GetRegion(bucket_name)
    if region == 'None':
        pass 
    else:
        print "Testing bucket {0}...".format(bucket_name)
        bucket = getBucket(bucket_name)
        results = "" 
        try:      
            for s3_object in bucket.objects.all():
                try:
                    if (MIN_SIZE < s3_object.get()["ContentLength"]) and \
                     ((s3_object.get()["ContentLength"] < MAX_SIZE) if MAX_SIZE else True)\
                     and re.match(REGEX, s3_object.key):
                    
                        item = "http://s3.{0}.amazonaws.com/{1}/{2}".format(\
                                   region, bucket_name, \
                                   s3_object.key.encode('utf-8'))
                        results += item + '\n'
                        print "Collectable: {0} {1}".format(item, size(s3_object.get()["ContentLength"]))         
                except Exception as e:
                     print "Error: couldn't get '{0}' object in '{1}' bucket. Details: {2}\n".format(s3_object.key.encode('utf-8'), bucket_name, e)
            
            appendOutput(results)
        except Exception as e:
            print "Error: couldn't access the '{0}' bucket. Details: {1}\n".format(bucket_name, e)

def writeTest(bucket_name, filename):
    region = GetRegion(bucket_name)
    if region != 'None':
        try:
            data = open(filename, 'rb')
            bucket = getBucket(bucket_name)
            bucket.put_object(Bucket=bucket_name, Key=filename, Body=data)
            print "Success: bucket '{0}' allows for uploading arbitrary files!!!".format(bucket_name.encode('utf-8'))
            results = "http://s3.{0}.amazonaws.com/{1}/{2}\n".format(region, bucket_name, filename)
            appendOutput(results)
        except Exception as e:
            print "Error: couldn't upload a {0} file to {1}. Details: {2}\n".format(filename, bucket_name, e)
        finally:
        	print "done"

def appendOutput(results):
    with open(OUTPUT_FILE, "a") as output:
        output.write(results)


def bucketWorker():
    while True:
        try:
            bucket = queue.get()
            bucketReader(bucket)
            if WRITE_TEST_ENABLED: writeTest(bucket, WRITE_TEST_FILE)
        except Exception as e:
            print "Error: {0}\n".format(e)
        queue.task_done()
    

def printHelp():
    print('''
--------------
BucketScanner
By @Rzepsky
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
-h: prints a help message.

====================== Example ======================

$ python BucketScanner.py -l bucket_list.txt -w upload_file.txt -r '^.*\.(db|sql)' -t 50 -m 5242880 -o output.txt


The above command will:
- test all buckets from bucket_list.txt file
- test if you can upload upload_file.txt to any of the bucket included in bucket_list.txt
- provide URLs in output.txt only to files bigger than 5 MB and with .db or .sql extension
- work on 50 threads
''')

def closingWords():
    print "That's all folks! All collectable files can be found in {0}.".format(OUTPUT_FILE)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-l", dest="bucket_list", required=True, help="a list with bucket names.") 
    parser.add_argument("-w", dest="write", type=str, required=False, default="", help="file to execute upload test.")
    parser.add_argument("-r", dest="regex", required=False, default='', help="regular expression filter")
    parser.add_argument("-s", dest="min", type=int, required=False, default=1, help="minimun size.")
    parser.add_argument("-m", dest="max", type=int, required=False, default=0, help="maximum size.")
    parser.add_argument("-t", dest="threads", type=int, required=False, default=10, help="thread count.")
    parser.add_argument("-o", dest="output", type=str, required=False, default="output.txt", help="output file.")

    if len(sys.argv) == 1:
        printHelp()
        sys.exit()
    arguments = parser.parse_args()
    if arguments.output is not "output.txt": setOutputFile(arguments.output)
    if arguments.write: setwriteTest(arguments.write)
    if arguments.regex: setRegex(arguments.regex)
    if arguments.min > 1: setMinsize(arguments.min)
    if arguments.max > 1: setMaxsize(arguments.max)
    if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY): setAnonymousMode()

    arguments = parser.parse_args()
    for i in range(0, arguments.threads):
        t = Thread(target=bucketWorker)
        t.daemon = True
        t.start()    
    
    with open(arguments.bucket_list, 'r') as f:
        for bucket in f:
            queue.put(bucket.rstrip())
        queue.join()

    closingWords()

