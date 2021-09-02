'''
Computer Vision Quickstart for Microsoft Azure Cognitive Services. 
Uses local and remote images in each example.

Prerequisites:
    - Install the Computer Vision SDK:
      pip install --upgrade azure-cognitiveservices-vision-computervision
    - Install PIL:
      pip install --upgrade pillow
    - Create folder and collect images: 
      Create a folder called "images" in the same folder as this script.
      Go to this website to download images:
        https://github.com/Azure-Samples/cognitive-services-sample-data-files/tree/master/ComputerVision/Images
      Add the following 7 images (or use your own) to your "images" folder: 
        faces.jpg, gray-shirt-logo.jpg, handwritten_text.jpg, landmark.jpg, 
        objects.jpg, printed_text.jpg and type-image.jpg

Run the entire file to demonstrate the following examples:
    - OCR: Read File using the Read API, extract text - remote
    - OCR: Read File using the Read API, extract text - local

References:
    - SDK: https://docs.microsoft.com/en-us/python/api/azure-cognitiveservices-vision-computervision/azure.cognitiveservices.vision.computervision?view=azure-python
    - Documentaion: https://docs.microsoft.com/en-us/azure/cognitive-services/computer-vision/index
    - API: https://westus.dev.cognitive.microsoft.com/docs/services/computer-vision-v3-2/operations/5d986960601faab4bf452005
'''

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials

import imghdr
from contextlib import redirect_stdout
from array import array
import os
from PIL import Image
import sys
import time
import json
import re
import os
import datetime
import logging
import mysql.connector
import schedule
from dotenv import load_dotenv
from re import compile


'''
Authenticate
Authenticates your credentials and creates a client.
'''
# Load config from env
load_dotenv()
subscription_key = os.getenv('SUBS_KEY')
endpoint = os.getenv('END_POINT')

# GCloud
mysql_host = os.getenv('DB_HOST')
mysql_db = os.getenv('DB_NAME')
mysql_db_cron = os.getenv('DB_NAME_CRON')
mysql_user = os.getenv('DB_USER')
mysql_password = os.getenv('DB_PW')
mysql_port = os.getenv('DB_PORT')
max_limit = os.getenv('MAX_LIMIT')

timer_start = None
timer_end = None

logname = datetime.datetime.now().strftime('LOG/OCR_Log_%d_%m_%Y.log')

computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))

# Images used for the examples: Describe an image, Categorize an image, Tag an image, 
# Detect faces, Detect adult or racy content, Detect the color scheme, 
# Detect domain-specific content, Detect image types, Detect objects
images_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

'''
OCR: Read File using the Read API, extract text - local
This example extracts text from a local image, then prints results.
This API call can also recognize remote image text (shown in next example, Read File - remote).
'''


logging.basicConfig(filename=logname,
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.DEBUG)


def connect_mysql(host, db, user, password, port):
    """
    Connect to mySQL database
    """
    try:
        connection = mysql.connector.connect(host=host, database=db, user=user, password=password, port=port)
        if connection.is_connected():
            print("Connected to MySQL")
            # logging.info("Connected to MySQL")
            return connection
    except NameError as e:
        print("Error while connecting to MySQL", e)
        # logging.error("Error while connecting to MySQL", e)


def get_eval():
    """
    Get evaluation data from specific database and table

    return:
    id, odometer, number, startDate
    """
    with open('get_eval.sql', 'r') as sql_file:
        query_file = sql_file.read()
        # print(query_file)
        connection = connect_mysql(mysql_host, mysql_db, mysql_user, mysql_password, mysql_port)
        db_cursor = connection.cursor()
        db_cursor.execute(query_file)
        myresult = db_cursor.fetchall()
        # logging.info(myresult)
        return myresult


def get_prev_eval(id, number):
    """
    Get previous evaluation data from specific database and table

    return:
    id, odometer, number, startDate
    """
    query_file = """select id,odometer,number,startDate 
                    from evaEvaluation
                    where deleted_at is null
                    and cpnAssign_id in (
                        select cpnAssign_id from evaEvaluation
                        where id = %s
                    )
                    and number < %s -- selected eval number
                    and status = 1
                    and odometer > 0
                    and verifiedAt is not null
                    order by number desc
                    limit 1""" %(id, number)
    connection = connect_mysql(mysql_host, mysql_db, mysql_user, mysql_password, mysql_port)
    db_cursor = connection.cursor()
    db_cursor.execute(query_file)
    myresult = db_cursor.fetchall()
    return myresult


def update_preprocess(id):
    """
    Update datetime before process to OCR Azure
    """
    query_file = """UPDATE `stickearn_mobil`.`evaEvaluation` 
                    SET `systemProcessedAt` = now()
                    WHERE (`id` = '%s');
                    """ %(id)

    connection = connect_mysql(mysql_host, mysql_db, mysql_user, mysql_password, mysql_port)
    db_cursor = connection.cursor()
    db_cursor.execute(query_file)
    connection.commit()
    # logging.info("Query pre-process updated!")
    print("Query pre-process updated!")


def autoverif_log(id, odo_result, odo_raw, odo_match, plate_result, plate_match, plate_raw, odo_finish, plate_finish):
    """
    Update all result to database
    """
    if odo_finish:
        global result_odo, raw_odo, match_odo
        result_odo = '''"%s"''' %(odo_result)
        raw_odo = '''"%s"''' %(odo_raw)
        match_odo = odo_match
    if plate_finish:
        result_plate = '''"%s"''' %(plate_result)
        match_plate = plate_match
        raw_plate = '''"%s"''' %(plate_raw)

        query_file = """INSERT INTO `stickearn_cron`.`auto_verify_logs`
                        (`evaluation_id`, `result`, `original_response`, `match`, `bw_result`, `bw_match`, `bw_original_response`, `created_at`, `updated_at`)
                        VALUES
                        (%s,%s,%s,%s,%s,%s,%s, now(), now());
                        """ %(id, result_odo, raw_odo, match_odo, result_plate, match_plate, raw_plate)

        # connection = connect_mysql(mysql_host, mysql_db_cron, mysql_user, mysql_password, mysql_port)
        # db_cursor = connection.cursor()
        # db_cursor.execute(query_file)
        # connection.commit()
        print("LOG TO DB: {}".format(query_file))
        print("Query all results updated!")
        # logging.info("LOG TO DB: {}".format(query_file))
        # logging.info("Query all results updated!")

        # Update OCR Verified when both ODO and Plate are suceeded
        # if match_odo and match_plate:
        #     update_ocr_verifAt(id)


def update_ocr_verifAt(id):
    """
    Update verified at specific time
    """
    query_file = """UPDATE `stickearn_mobil`.`evaEvaluation` 
                    SET `ocrVerifiedAt` = now()
                    WHERE (`id` = %s);
                    """ %(id)

    connection = connect_mysql(mysql_host, mysql_db, mysql_user, mysql_password, mysql_port)
    db_cursor = connection.cursor()
    db_cursor.execute(query_file)
    connection.commit()
    # logging.info("OCR VERIFIED AT: Query all results updated!")
    print("OCR VERIFIED AT: Query all results updated!")

    
def get_eval_photo(id):
    """
    Get photo_id and image URL from specific database and table

    return:
    photo_id (1 for odometer, 2 for plate number)
    """
    query_file = """select evaEvaluation_id,masPhotoPosition_id,imageURL from evaPhoto
                    where evaEvaluation_id in (%s)
                    and deleted_at is null
                    and masPhotoPosition_id in (1,2)""" %(id)

    connection = connect_mysql(mysql_host, mysql_db, mysql_user, mysql_password, mysql_port)
    db_cursor = connection.cursor()
    db_cursor.execute(query_file)
    myresult = db_cursor.fetchall()
    return myresult

    
def get_vehicle_plate(id):
    """
    Get plate number of vehicle from specific database and table

    return:
    vehicle plate number
    """
    query_file = """select licenseNumber from drvVehicle
                    where id in (
                        select drvVehicle_id from drvVehicleOwnership
                        where id in (
                            select drvVehicleOwnership_id from cpnAssign
                            where id in (
                                select cpnAssign_id from evaEvaluation
                                where id = (%s)
                                and deleted_at is null
                            )
                            and deleted_at is null
                        )
                        and active = 1
                        and deleted_at is null
                    )
                    and deleted_at is null""" %(id)
    connection = connect_mysql(mysql_host, mysql_db, mysql_user, mysql_password, mysql_port)
    db_cursor = connection.cursor()
    db_cursor.execute(query_file)
    myresult = db_cursor.fetchall()
    return myresult


def ocr_process():
    """
    Get all necessary data
    Put in on a list for each id
    Extract all data with OCR
    """
    # timer_start = time.time()

    for eval in get_eval():
        id = eval[0]
        odo = eval[1]
        number = eval[2]
        startDate = eval[3]

        print("*************************************")
        print("ID: {}".format(id))
        # print("ODO: {}".format(odo))
        # print("Number: {}".format(number))
        # print("StartDate: {}".format(startDate))
        logging.info("ID: {}".format(id))

        for prev_eval in get_prev_eval(id, number):
            prev_id = prev_eval[0]
            prev_odo = prev_eval[1]
            prev_number = prev_eval[2]
            prev_startDate = prev_eval[3]

            # print("\nPrev ID: {}".format(prev_id))
            # print("Prev ODO: {}".format(prev_odo))
            # print("Prev Number: {}".format(prev_number))
            # print("Prev StartDate: {}".format(prev_startDate))

            delta = startDate - prev_startDate
            odo_diff = odo - prev_odo
            try:
                max_count = odo_diff / delta.days

                print("Elapse days: {}".format(delta.days))
                print("ODO Diff: {}".format(odo_diff))
                print("Max Count: {}".format(max_count))
                logging.info("Elapse days: {}".format(delta.days))
                logging.info("ODO Diff: {}".format(odo_diff))
                logging.info("Max Count: {}".format(max_count))

                if max_count < float(max_limit):
                    for eval_photo in get_eval_photo(id):
                        photo_id = eval_photo[1]
                        i_url = eval_photo[2]

                        for vehicle_plate in get_vehicle_plate(id):
                            plate = vehicle_plate[0]

                            print("\nID: %s" %(id))
                            print("ODO: %s" %(odo))
                            print("Photo ID: %s" %(photo_id))
                            print("Image URL: %s" %(i_url))
                            print("Plate Number: %s\n" %(plate))
                            logging.info("\nID: %s" %(id))
                            logging.info("ODO: %s" %(odo))
                            logging.info("Photo ID: %s" %(photo_id))
                            logging.info("Image URL: %s" %(i_url))
                            logging.info("Plate Number: %s\n" %(plate))

                            # Run OCR Process
                            extract_data(id, odo, photo_id, i_url, plate)

                            # Estimate time per itteration
                            # elapsed_time = int(time.time() - timer_start)
                            # print("Time per itteration: {}\n\n".format(elapsed_time))
                            # logging.info("Time per itteration: {}\n\n".format(elapsed_time))
                            # elapsed_time = 0

            except ZeroDivisionError:
                print("Delta days Zero: {}".format(delta.days))


def extract_data(id, odo, photo_id, i_url, plate):
    """
    Process image URL with Azure OCR

    return:
    odo compare result
    plate number compare result
    """
    count = 0
    extract_line_odo = None
    raw_extract_odo = ""
    extract_line_plate = None
    raw_extract_plate = ""
    pattern_odo = None
    pattern_plate = None
    odo_matched = "not matched"
    plate_matched = "not matched"
    odo_json = False
    plate_json = False
    odo_finish = False
    plate_finish = False

    id = id
    odo = str(odo)
    photo_id = photo_id
    i_url = i_url
    plate = plate
    line_str = None

    raw_odo = ""
    raw_plate = ""

    try:
        # Call API with URL and raw response (allows you to get the operation location)
        read_response = computervision_client.read(i_url,  raw=True)

        # Get the operation location (URL with an ID at the end) from the response
        read_operation_location = read_response.headers["Operation-Location"]

        # Grab the ID from the URL
        operation_id = read_operation_location.split("/")[-1]

        # Call the "GET" API and wait for it to retrieve the results 
        while True:
            read_result = computervision_client.get_read_result(operation_id)
            if read_result.status not in ['notStarted', 'running']:
                break
            time.sleep(1)

        # Print results, line by line
        if read_result.status == OperationStatusCodes.succeeded:
            for text_result in read_result.analyze_result.read_results:
                # Put sql command to update table here
                datenow = datetime.datetime.now()
                # print("Update to ocr systemProcessedAt: %s" % (datenow))
                # update_preprocess(id)
                # print("PRE-PROCESS UPDATED!")
                print("Raw result: ", end="")

                # ODOMETER
                if photo_id == 1:
                    odo_finish = True
                    for line in text_result.lines:
                        line_str = str(line.text) # line_str can use to update raw result
                        # print(line_str)
                        raw_odo += line_str
                        print(raw_odo)
                        # Remove non-alphanumeric char
                        pattern_odo = re.compile('\W')
                        extract_line_odo = re.sub(pattern_odo, '', line_str)
                        # print('Extracted: ', end="")
                        # print(extract_line_odo)
                        odo = odo.replace(' ','')

                        if extract_line_odo.isalnum() and len(extract_line_odo) >= 4:
                            extract_line_odo = re.findall("\d+", extract_line_odo)  # extract_line_odo can use as matched result
                            raw_extract_odo = (raw_extract_odo.join(extract_line_odo))
                            extract_odo = re.findall("\d+", odo)
                            print('Extracted alnum ODO: ', end="")
                            print(raw_extract_odo)

                            for x, y in zip(extract_line_odo, extract_odo):
                                for a, b in zip(x, y):
                                    if a in y:
                                        count += 1
                            if count >= 3:
                                count = 0
                                odo_matched = "matched"
                                odo_json = True # use this line to update database
                                break

                # PLATE NUMBER
                if photo_id == 2:
                    for line in text_result.lines:
                        line_str = str(line.text) # line_str can use to update raw result
                        raw_plate += line_str
                        print(raw_plate)
                        # Remove non-alphanumeric char
                        pattern_plate = re.compile('\W')
                        extract_line_plate = re.sub(pattern_plate, '', line_str)  # extract_line_plate can use as matched result
                        # print('Extracted line: ', end="")
                        # print(extract_line_plate)
                        plate = plate.replace(' ','')
                        plate_finish = True

                        if extract_line_plate.isalnum() and len(extract_line_plate) >= 4:
                            extract_line_plate = re.findall("\d+", extract_line_plate)
                            raw_extract_plate = (raw_extract_plate.join(extract_line_plate))
                            extract_plate = re.findall("\d+", plate)
                            print('Extracted plate: ', end="")
                            print(extract_line_plate)

                            for x, y in zip(extract_line_plate, extract_plate):
                                for a, b in zip(x, y):
                                    if a in y:
                                        count += 1
                            if count >= 2:
                                count = 0
                                plate_matched = "matched"
                                plate_json = True # use this line to update database
                                break

            autoverif_log(id, raw_extract_odo, raw_odo, odo_json*1, raw_extract_plate, plate_json*1, raw_plate, odo_finish, plate_finish)
            if odo_finish:
                print("Result:")
                print('Odo input: {}'.format(odo))
                print('Odo result: {}'.format(raw_extract_odo))
                print('Odo status: {}'.format(odo_matched))
                logging.info("Result:")
                logging.info('Odo input: {}'.format(odo))
                logging.info('Odo result: {}'.format(raw_extract_odo))
                logging.info('Odo status: {}'.format(odo_matched))
                odo_json = False
                odo_matched = "not matched"
            if plate_finish:
                print('Plate input: {}'.format(plate))
                print('Plate result: {}'.format(extract_line_plate))
                print('Plate status: {}'.format(plate_matched))
                logging.info("Result:")
                logging.info('Plate input: {}'.format(plate))
                logging.info('Plate result: {}'.format(extract_line_plate))
                logging.info('Plate status: {}'.format(plate_matched))
                plate_json = False
                plate_matched = "not matched"
            print('*************************************\n')
        else:
            print('Picture not clear enough to process.\n\n')
            logging.info('Picture not clear enough to process.\n\n')

    except NameError as e:
        print("Failed to process image!", e)
        logging.error("Failed to process image!", e)


if __name__ == "__main__":
    # schedule.every(1).minutes.do(ocr_process)
    # while True:
    #     print("Waiting for next schedule..")
    #     schedule.run_pending()
    #     time.sleep(1)

    # print(get_eval())
    ocr_process()