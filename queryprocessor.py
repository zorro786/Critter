#
# Copyright (C) 2016 University of Southern California.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License,
# version 2, as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
import json
import logging
import os
import urlparse
from datetime import datetime
import requests
import critter_settings
from critter_settings import settings


#Initialise the logger
query_logger = logging.getLogger("QueryLogger")
hdlr = logging.FileHandler(critter_settings.USER_DIR + '/critter.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
query_logger.addHandler(hdlr)
query_logger.setLevel(logging.INFO)

class Query:
    def __init__(self):
        self.request_id = None
        self.request_title = None
        self.request_body = None
        self.response_result = None
        self.submission_date = None
        self.sql = critter_settings.init()

    def run_query(self):
        query_logger.info("Running Query: %s " % (self.request_body))
        result = self.sql.request_query(self.request_body, None)
        if len(result) > 1:
            query_logger.info("More than one count row in query, probably unsupported Group By clause used")
            return
        #if result[0][0] == 0:
        #    query_logger.info("0 returned. Result will not be sent")
        #    return
        else:
            query_logger.info("Query Answer: %s" % (result[0][0]))
            self.response_result = result[0][0]


class FetchQueries():
    def clean_sql_statement(self, string):
        res = ""
        char = "'"
        if string.startswith(char) and string.endswith(char):
            res += string[1:-1]
        elif string.startswith(char):
            res += string[1:]
        elif string.endswith(char):
            res += string[:-1]
        res.strip().strip("\n")
        return res

    def retrieve_queries(self):
        login_result = login()
        fetched_queries = []
        if login_result['isSuccessfull']:
            cookies = login_result.get('cookies')
            try:
                fetch_queries_url = urlparse.urljoin(settings.server_addr, "fetchallqueries.php")
                r = requests.post(fetch_queries_url, cookies=cookies)
                jsonResponse = r.json()
                if jsonResponse['retCode'] == 0:
                    fetch_request_result = {'isSuccessfull': True, 'queries': jsonResponse['queries'],
                                            'errorMessage': '', 'serverResponse': ''}
                else:
                    fetch_request_result = {'isSuccessfull': False, 'queries': None,
                                            'errorMessage': jsonResponse['errorDescription'],
                                            'serverResponse': ''}
            except ValueError:
                fetch_request_result = {'isSuccessfull': False, 'cookies': None,
                                        'errorMessage': 'Unknown Error in fetchQueries',
                                        'serverResponse': r.text}
            except requests.exceptions.RequestException:
                fetch_request_result = {'isSuccessfull': False, 'cookies': None,
                                        'errorMessage': 'Connect To Critter Server Failed',
                                        'serverResponse': 'requestException'}
            if fetch_request_result['isSuccessfull']:
                fetched_queries = fetch_request_result['queries']
            else:
                print fetch_request_result['errorMessage'] + fetch_request_result['serverResponse']
                return

        else:
            logging.info("User Login Failure: " + login_result[
                'errorMessage'] + ' ::' + login_result['serverResponse'])
            return

        return self.process_queries(fetched_queries)

    def process_queries(self, fetched_queries):
        """This function creates a Query object for each query in fetched_queries after processing, and runs it against DB.
        """
        queries = []
        for fetched_query in fetched_queries:
            query = Query()
            query.request_id = fetched_query["request_id"].strip("'")
            query.request_title = fetched_query["request_title"].strip("'")
            query.request_body = self.clean_sql_statement(fetched_query["request_body"])
            queries.append(query)
            """try:
                is_valid, msg = is_sql_valid(query.request_body)
                if(not is_valid):
                    logging.error('SQLValidator: Bad Query:: Reason: %s:: SQL: %s' % msg, query.request_body)
                else:
                    queries.append(query)
            except:
                logging.exception(
                    'SQLValidator: Exception while parsing query %s'
                    % (query.request_body))"""
        queries = self.check_history(queries)
        for q in queries:
            q.run_query()

        return queries


    def check_history(self, processed_queries):
        """This function checks the processed queries against history file, removes those that are up to date and returns out dated queries.
           These outdated queries will be written in history file later.
        """
        if not os.path.isfile(settings.query_history_file_name):
            open(settings.query_history_file_name, 'w').close()
        f = open(settings.query_history_file_name, 'rU')
        lines = f.readlines()
        f.close()
        queries_already_run = [line.strip('\n') for line in lines]
        outdated_queries = []
        queries_already_run_json = []
        query_ids_not_to_run = []
        for query_already_run in queries_already_run:
            query = json.loads(query_already_run)
            queries_already_run_json.append(query)
            query_timestmp = datetime.strptime(query['previousRunTime'],
                                               '%Y-%m-%dT%H:%M:%S')

            if (datetime.now() - query_timestmp).seconds > critter_settings.QUERY_RUN_FREQUENCY:
                outdated_queries.append(query)
            else:
                query_ids_not_to_run.append(query['request_id'])

        for outdated_query in outdated_queries:
            if (outdated_query in queries_already_run_json):
                queries_already_run_json.remove(outdated_query)

        if (len(outdated_queries) > 0):
            f = open(settings.query_history_file_name, 'w')
            for query_already_run_json in queries_already_run_json:
                f.write(json.dumps(query_already_run_json) + "\n")
            f.close()

        for processed_query in processed_queries:
            if (str(processed_query.request_id) in query_ids_not_to_run):
                processed_queries.remove(processed_query)

        return processed_queries


class SendResults:
    def process_results(self, queries):
        """This function takes input as the processed queries which were run against DB, submits responses to server and writes the queries submitted
        in history file.
        """
        queries_with_result = [q for q in queries if q.response_result is not None]
        login_result = login()
        # first login to critter server & then fetch queries
        if login_result['isSuccessfull']:
            query_logger.info("User Login successfull")
            responses = []
            for query_with_result in queries_with_result:
                responses.append({
                    "request_id": query_with_result.request_id,
                    "response": query_with_result.response_result})
            if (len(responses) > 0):
                submission_result = self.submit_responses(login_result['cookies'], responses)
                if submission_result['isSuccessfull']:
                    query_logger.info("Submit Responses successfull")
                    f = open(settings.query_history_file_name, 'a') #Write the queries run in the history file
                    for submitted_response in responses:
                        current_timestmp = datetime.now()
                        f.write(json.dumps({'previousRunTime': current_timestmp.strftime('%Y-%m-%dT%H:%M:%S'),
                                            'request_id': submitted_response['request_id']}) + "\n")
                    f.close()
                else:
                    query_logger.info(
                        "Responses Submission Failure:" +
                        submission_result['errorMessage'] +
                        submission_result['serverResponse'])
                    query_logger.info(
                        "Responses not submitted: " +
                        str(submission_result['failedResponses']))
            else:
                query_logger.info("Nothing to submit!")

    def submit_responses(self, cookies, responses):
        payload = {'responses_data': json.dumps({'responses': responses})}
        try:
            submit_responses_url = urlparse.urljoin(settings.server_addr, "submitresponses.php")
            r = requests.post(submit_responses_url, cookies=cookies, data=payload)
            json_response = r.json()
            if json_response['retCode'] == 0:
                return {'isSuccessfull': True, 'failedResponses': [],
                        'errorMessage': '', 'serverResponse': ''}
            elif json_response['retCode'] == 100:
                # there was an error in submitting some responses
                failedResponses = []
                requestIds = []
                for failedResponse in json_response['responses_not_uploaded']:
                    requestIds.append(failedResponse['request_id'])
                for response in responses:
                    if response['request_id'] in requestIds:
                        failedResponses.append(response)
                return {'isSuccessfull': False, 'failedResponses': failedResponses,
                        'errorMessage': json_response['errorDescription'],
                        'serverResponse': ''}
            else:
                return {'isSuccessfull': False, 'failedResponses': responses,
                        'errorMessage': json_response['errorDescription'],
                        'serverResponse': r.text}
        except ValueError:
            return {'isSuccessfull': False, 'cookies': None,
                    'failedResponses': responses,
                    'errorMessage': 'Json Decode Error in submitResponses',
                    'serverResponse': r.text}
        except requests.exceptions.RequestException:
            return {'isSuccessfull': False, 'cookies': None,
                    'failedResponses': responses,
                    'errorMessage': 'Connect To Critter Server Failed',
                    'serverResponse': 'requestException'}


def login():
    """This function logs in to the server using settings from critter_settings file.
    """
    payload = {'user': settings.username, 'password': settings.password}
    try:

        login_url = urlparse.urljoin(settings.server_addr, "loginbackend.php")
        r = requests.post(login_url, data=payload)
        if "Successfully Logged in" in r.text:
            return {'isSuccessfull': True, 'cookies': r.cookies, 'errorMessage': '',
                    'serverResponse': ''}
        elif "Bad Username or Password" in r.text:
            return {'isSuccessfull': False, 'cookies': None,
                    'errorMessage': 'Bad Username or Password',
                    'serverResponse': ''}
        else:
            return {'isSuccessfull': False, 'cookies': None,
                    'errorMessage': 'Unknown Error in doLogin',
                    'serverResponse': r.text}
    except requests.exceptions.RequestException:
        return {'isSuccessfull': False, 'cookies': None,
                'errorMessage': 'Connect To Critter Server Failed',
                'serverResponse': 'requestException'}


def update_k_value():
    """This function updates K anonymity value of the user at the server.
    """
    login_result = login()
    if (login_result['isSuccessfull']):
        query_logger.info("User Login successfull")
    else:
        query_logger.info("User Login failed")
    payload = {'k_value': settings.k_value}
    try:
        k_value_update_url = urlparse.urljoin(settings.server_addr, "updatekvalue.php")
        r = requests.post(k_value_update_url, cookies=login_result['cookies'], data=payload)
        if "K value updated successfully" in r.text:
            query_logger.info("K value updated successfully")
            return {'isSuccessfull' : True}
        else:
            query_logger.info("K value update failed")
            return{'isSuccessfull' : False, 'errorMessage' : r.text}
    except requests.exceptions.RequestException:
        query_logger.info("Connect to Critter Server Failed")
        return {'isSuccessfull' : False, 'errorMessage' : "Connect to Critter Server Failed"}

def queryprocessor_worker():
    fetchqueries = FetchQueries()
    queries = fetchqueries.retrieve_queries()
    if (queries is None):
        return
    sendresults = SendResults()
    sendresults.process_results(queries)
