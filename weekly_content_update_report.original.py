import csv
import json
import socket
import sys
import urllib
import urllib2
from calendar import timegm
from datetime import datetime, timedelta

def main(argv=None):

    #portal_url = 'http://inteam.maps.arcgis.com'
    #username = 'JulieDemo_inteam'
    #password = 'euds'

    portal_url = 'http://esriesdemo1012.maps.arcgis.com'
    username = 'javier.abadia.demo1012'
    password = ''

    # Setup the URLs used to connect to portal
    rest_url = portal_url + '/sharing/rest'
    secure_rest_url = rest_url.replace('http://', 'https://')

    # Generate a token (if username and password are provided)
    token = None
    if username and password:
        token = get_token(secure_rest_url, username, password)

    print "# PORTAL:  ", portal_url
    print "# USUARIO: ", username
    print "# TOKEN:   ",token

    # Retrieve the portal properties, and switch to using HTTPS only if
    # the portal is configured to all SSL
    portal_properties = get_portal_properties(secure_rest_url, token)
    if portal_properties.get('allSSL'):
        rest_url = secure_rest_url

    # Prepare the query that checks for things modified within the last week.
    # Also append the org's ID to restrict searches to within the organization.
    today = datetime.utcnow()
    weekago = today - timedelta(weeks=4)
    q = 'modified:[' + portal_time(weekago) + ' TO ' + portal_time(today) + ']'
    org_id = portal_properties.get('id')
    if org_id:
        q += ' accountid:' + org_id

    # Search the portal, making a call  for each "page" of results
    results, next_start = search(rest_url, q, 1, 100, token)
    while next_start > 0:
        page_results, next_start = search(rest_url, q, next_start, 100, token)
        results.extend(page_results)

    # Loop over the results and write them to a CSV file
    fields = ['id', 'title', 'owner', 'numViews']
    csvfile = csv.writer(open('weekly-content-update-report.csv', 'wb'))
    csvfile.writerow(fields)
    for item in results:
        row = [item[field] for field in fields]
        row = [(field.encode('utf-8') if isinstance(field,unicode) else field) for field in row]
        csvfile.writerow(row)
        #print row

    #get list of groups
    groups = get_gropus(rest_url, token)
    print groups

def get_token(rest_url, username, password):
    ip = socket.gethostbyname(socket.gethostname())
    referer = socket.gethostbyaddr(ip)[0]
    postdata = { 'username': username, 'password': password,\
                 'client': 'referer', 'referer': referer,\
                 'expiration': 60, 'f': 'json' }
    resp = send_post_request(rest_url + '/generateToken', postdata)
    return resp['token']

def get_portal_properties(rest_url, token):
    postdata = { 'f': 'json' }
    if token:
        postdata['token'] = token
    return send_post_request(rest_url + '/portals/self', postdata)

def portal_time(dt):
    # Turns a UTC datetime object into portal's date/time string format.
    return '000000' + str(timegm(dt.timetuple()) * 1000)

def search(rest_url, q, start, num, token):
    postdata = { 'q': q, 'start': start, 'num': num, 'f': 'json' }
    if token:
        postdata['token'] = token
    resp = send_post_request(rest_url + '/search', postdata)
    return resp['results'], resp['nextStart']

def send_post_request(url, postdata):
    request = urllib2.urlopen(url, urllib.urlencode(postdata))
    print '=='
    print url
    print postdata
    print '-'
    response = json.loads(request.read(),'utf-8')
    print response
    if 'error' in response:
        error_message = response['error']['message']
        print error_message
        for error_detail in response['error']['details']:
            print error_detail
        raise StandardError('Portal error: ' + error_message)
    return response

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
