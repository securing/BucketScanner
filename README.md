BucketScanner (by @Rzepsky)
========================================

BucketScanner is a tool used to:

* find collectable files for an anonymous/authenticated user in your buckets
* verify if an anonymous/authenticated user is allowed to upload arbitrary files to your buckets


### Oh my gosh... another AWS bucket scanner!?

Surprisingly I haven't found a one tool which has all these features:

1. supports authenticated requests.
2. checks a bucket even if you don't have 'ListBucket' permissions (I found examples when a bucket policy allows for downloading files, however in the reply to GET request to the bucket I got 403 code).
3. the verbose mode is printed out on the terminal window while in the output file you can find URLs to only collectable files (when you work on big amounts of files it can save you a lot of time)
4. supports test for uploading a file.
5. supports regular expressions (to filter out only interesting files).
6. supports minimum and maximum size filters.
7. supports multithreading.

### Usage

```
BucketScanner.py -l BUCKET_LIST [-w WRITE_TEST_FILE] [-r REGEX]  [-s MIN_SIZE] [-m MAX_SIZE] [-t THREADS] [-o OUTPUT_FILE] [-h HELP]
```

### Command line options

* `-l <filename>` - specify a list with bucket names to check.
* `-w <filename>` - specify a file to upload to a bucket.
* `-r <regex expresion>` - specify a regular expression to filter the output.
* `-s <minimum size>` - look only for files bigger than 's' bytes
* `-m <maximum size>` - look only for files smaller than 'm' bytes 
* `-t <threads>` - number of threads to run (default: `10`).
* `-o <filename>` - specify an output file for collectable URLs.
* `-h` - prints a help message.

> Please note that to use authenticated requests you have to specify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` variables in BucketScanner.py file.

### Example

```
$ python BucketScanner.py -l bucket_list.txt -w upload_file.txt -r '^.*\.(db|sql)' -t 50 -s 5242880 -o output.txt
```
Using the above command, a BucketScanner will:

* test all buckets from `bucket_list.txt` file
* test if you can upload `upload_file.txt` to any of the bucket included in `bucket_list.txt`
* provide URLs in output.txt only to files bigger than 5 MB and with `.db` or `.sql` extension
* work on 50 threads

### Pre-requisites
To run the BucketScanner you have to install python `boto3` and `requests` libraries. You can do this by running the following command:

```
pip install -r requirements.txt
```

### License

See the LICENSE file.
