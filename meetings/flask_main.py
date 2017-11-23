import flask
from flask import render_template
from flask import request
from flask import url_for
import uuid

import json
import logging

# Date handling
import arrow  # Replacement for datetime, based on moment.js
# import datetime # But we still need time
from dateutil import tz  # For interpreting local times


# OAuth2  - Google library implementation for convenience
from oauth2client import client
import httplib2   # used in oauth2 flow

# Google API for services
from apiclient import discovery

import model
from math import ceil
###
# Globals
###
import config
if __name__ == "__main__":
  CONFIG = config.configuration()
else:
  CONFIG = config.configuration(proxied=True)

app = flask.Flask(__name__)
app.debug = CONFIG.DEBUG
app.logger.setLevel(logging.DEBUG)
app.secret_key = CONFIG.SECRET_KEY

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = CONFIG.GOOGLE_KEY_FILE  # You'll need this
APPLICATION_NAME = 'MeetMe class project'

DBconfig = model.DB_config(CONFIG.DB_USER,
    CONFIG.DB_USER_PW,
    CONFIG.DB_HOST, 
    CONFIG.DB_PORT, 
    CONFIG.DB)

DB = model.DB(DBconfig)
gen = DB.collection_name_gen()

def get_range():
  duration = flask.session.get('duration')
  if duration:
    Set_range = model.eventrange(flask.session['begin_date'], flask.session['end_date'], duration)
  else:
    Set_range = model.eventrange(flask.session['begin_date'], flask.session['end_date'])
  return Set_range

def get_users_selected():
  pass

#############################
#
#  Pages (routed from URLs)
#
#############################


@app.route("/")
@app.route("/index")
def index():
  app.logger.debug("Entering index")
  return render_template('index.html')


@app.route("/inviter")
def inviter():
    # We'll need authorization to list calendars
    # I wanted to put what follows into a function, but had
    # to pull it back here because the redirect has to be a
    # 'return'
  update_session_from_DB()
  update_session_to_DB()

  Set_range = get_range()
  flask.g.users = []
  for collection in DB.all_user_collection():
      if "MeetingUser" in collection:
        flask.g.users.append(collection)
        DB.set_collection(collection)
        for event in DB.get_all():
          test_record = model.record(None, None, event)
          test_event = model.calendar_event(test_record.start, test_record.end)
          Set_range.blockage.append(test_event)
  Set_range.subtract_blockage()
  flask.flash(str(Set_range))
  return render_template('inviter.html')

@app.route("/invitee")
def invitee():
    # We'll need authorization to list calendars
    # I wanted to put what follows into a function, but had
    # to pull it back here because the redirect has to be a
    # 'return'

  update_session_from_DB()
  giving_user_default_name()

  app.logger.debug("Checking credentials for Google calendar access")
  credentials = valid_credentials()
  if not credentials:
    app.logger.debug("Redirecting to authorization")
    return flask.redirect(flask.url_for('oauth2callback'))

  gcal_service = get_gcal_service(credentials)
  app.logger.debug("Returned from get_gcal_service")
  
  flask.g.calendars = list_calendars(gcal_service)
  flask.g.busy_list = get_busy(gcal_service, flask.g.calendars)
  
  return render_template('invitee.html')

#####
#
#  Option setting:  Buttons or forms that add some
#     information into session state.  Don't do the
#     computation here; use of the information might
#     depend on what other information we have.
#   Setting an option sends us back to the main display
#      page, where we may put the new information to use.
#
#####


@app.route('/setrange', methods=['POST'])
def setrange():
  """
  User chose a date range with the bootstrap daterange
  widget.
  """
  app.logger.debug("Entering setrange")
  # delete previous attendent
  delete_all_attendent()

  daterange = request.form.get('daterange')
  daterange_parts = daterange.split()

  begin_date = daterange_parts[0] + " " + flask.session['begin_time']
  end_date = daterange_parts[2] + " " + flask.session['end_time']
  flask.session['begin_date'] = interpret_date(begin_date)
  flask.session['end_date'] = interpret_date(end_date)
  duration = flask.session.get('duration')
  if not duration:
    flask.session['duration'] = 30

  update_session_to_DB()
  return flask.redirect(flask.url_for("inviter"))

####
#
#   Initialize session variables
#
####

def interpret_date(text):
  """
  Convert text of date to ISO format used internally,
  with local timezone
  """
  try:
    as_arrow = arrow.get(text, "MM/DD/YYYY HH:mm").replace(
        tzinfo=tz.tzlocal())
  except:
    flask.flash("Date '{}' didn't fit expected format 12/31/2001")
    raise
  return as_arrow.isoformat()

def next_day(isotext):
  """
  ISO date + 1 day (used in query to Google calendar)
  """
  as_arrow = arrow.get(isotext)
  return as_arrow.replace(days=+1).isoformat()

def delete_all_attendent():
  for collection in DB.all_user_collection():
      if "MeetingUser_" in collection:
        DB.set_collection(collection)
        DB.del_collection()

def update_session_to_DB():
  # new range set, add to db; invitee side will read time range from db
  DB.set_collection("meeting_time")
  DB.del_collection()
  DB.set_collection("meeting_time")

  begin_date = flask.session["begin_date"]
  end_date = flask.session["end_date"]
  duration = flask.session["duration"]
  # clear previous range
  DB.insert(model.record(begin_date, end_date, duration))

def update_session_from_DB():
  DB.set_collection("meeting_time")
  last_meeting_set = DB.get_all()
  if len(last_meeting_set) == 0:
    now = arrow.now('local').floor('day')

    # Default time span (hh : min) ~ (hh + 2 : min)
    flask.session["begin_time"] = now.format("HH:mm")
    flask.session["end_time"] = now.shift(hours=2).format("HH:mm")

    tomorrow = now.replace(days=+1)
    nextweek = now.replace(days=+7)
    flask.session["begin_date"] = tomorrow.isoformat()
    flask.session["end_date"] = nextweek.isoformat()
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
    flask.session["duration"] = 30
  else:
    last_meeting_set = model.record(None, None, last_meeting_set[0])
    flask.session["begin_date"] = last_meeting_set.start
    flask.session["end_date"] = last_meeting_set.end

    start = arrow.get(flask.session["begin_date"])
    end = arrow.get(flask.session["end_date"])
    flask.session["begin_time"] = start.format("HH:mm")
    flask.session["end_time"] = end.format("HH:mm")

    tomorrow = start.replace(days=+1)
    nextweek = start.replace(days=+7)
    flask.session["daterange"] = "{} - {}".format(
        tomorrow.format("MM/DD/YYYY"),
        nextweek.format("MM/DD/YYYY"))
  flask.g.begin_date = flask.session["begin_date"].split('T')[0]
  flask.g.begin_hour = flask.session["begin_time"].split(':')[0]
  flask.g.begin_minute = flask.session["begin_time"].split(':')[1]
  flask.g.end_hour = flask.session["end_time"].split(':')[0]
  flask.g.end_minute = flask.session["end_time"].split(':')[1]
  flask.g.end_date = flask.session["end_date"].split('T')[0]
  flask.g.duration = flask.session["duration"]

def giving_user_default_name():
  DB.set_collection("You_forgot_to_set_collection")
  false_record = model.record("false", "hood")
  DB.insert(false_record)
  while True:
    attempt = next(gen)
    if DB.rename_collection(attempt):
      flask.session["userid"] = attempt
      flask.g.userid = attempt
      break
  DB.del_record(false_record)

def reading_user_busy_time():
  app.logger.debug("Checking credentials for Google calendar access")
  credentials = valid_credentials()
  if not credentials:
    app.logger.debug("Redirecting to authorization")
    return flask.redirect(flask.url_for('oauth2callback'))

  gcal_service = get_gcal_service(credentials)
  app.logger.debug("Returned from get_gcal_service")
  
  flask.g.calendars = list_calendars(gcal_service)
  flask.g.busy_list = get_busy(gcal_service, flask.g.calendars)
####
#
#  Functions (NOT pages) that return some information
#
####


def get_busy(service, calendars):
  Set_range = get_range()
  DB.set_collection(flask.session["userid"])
  items = []
  keys = []

  body = {
      "timeMin": flask.session["begin_date"],
      "timeMax": flask.session["end_date"],
  }

  for calendar in calendars:
    if calendar['selected']:
      items.append({"id": calendar['id']})
      keys.append(calendar['id'])

  body["items"] = items

  app.logger.debug("Body is like " + str(body))

  busy_list = service.freebusy().query(body=body).execute()["calendars"]

  results = []
  for key in keys:
    for chunk in busy_list[key]['busy']:
      tmp_event = model.calendar_event(chunk['start'], chunk['end'])
      if tmp_event.compare_to(Set_range) == model.event_compare_result.within:
        DB.insert(model.record(chunk['start'], chunk['end']))
    results.append(busy_list[key]['busy'])

  return results


def list_calendars(service):
  """
  Given a google 'service' object, return a list of
  calendars.  Each calendar is represented by a dict.
  The returned list is sorted to have
  the primary calendar first, and selected (that is, displayed in
  Google Calendars web app) calendars before unselected calendars.
  """
  app.logger.debug("Entering list_calendars")
  calendar_list = service.calendarList().list().execute()["items"]
  result = []
  Calendars_checked = flask.session.get("Checked_cals")
  for cal in calendar_list:
    kind = cal["kind"]
    id = cal["id"]
    if "description" in cal:
      desc = cal["description"]
    else:
      desc = "(no description)"
    summary = cal["summary"]
    selected = False
    # Optional binary attributes with False as default

    if not Calendars_checked or Calendars_checked[id]:
      app.logger.debug("Calendars_checked " + str(Calendars_checked))
      selected = True
    primary = ("primary" in cal) and cal["primary"]

    result.append(
        {"kind": kind,
         "id": id,
         "summary": summary,
         "selected": selected,
         "primary": primary
         })
    app.logger.info(str(result))
  return sorted(result, key=cal_sort_key)


def cal_sort_key(cal):
  """
  Sort key for the list of calendars:  primary calendar first,
  then other selected calendars, then unselected calendars.
  (" " sorts before "X", and tuples are compared piecewise)
  """
  if cal["selected"]:
    selected_key = " "
  else:
    selected_key = "X"
  if cal["primary"]:
    primary_key = " "
  else:
    primary_key = "X"
  return (primary_key, selected_key, cal["summary"])


#################
#
# Functions used within the templates
#
#################

@app.template_filter('fmtdate')
def format_arrow_date(date):
  try:
    normal = arrow.get(date)
    return normal.format("ddd MM/DD/YYYY")
  except:
    return "(bad date)"


@app.template_filter('fmttime')
def format_arrow_time(time):
  try:
    normal = arrow.get(time)
    return normal.format("HH:mm")
  except:
    return "(bad time)"


@app.route('/_updateTimeRange', methods=['GET', 'POST'])
def _update_time_range():
  app.logger.debug("Got a updating time range request.")
  timeranges = request.get_json()
  begin_time = timeranges['hour1'] + ':' + timeranges['min1']
  end_time = timeranges['hour2'] + ':' + timeranges['min2']

  flask.session["begin_time"] = begin_time
  flask.session["end_time"] = end_time
  return flask.jsonify(success=True)


@app.route('/_updateDuration', methods=['GET', 'POST'])
def _update_duration():
  result = request.get_json()['duration']
  if result.isdigit():
    result = ceil(float(result))
    flask.session["duration"] = result
    app.logger.debug("Got a updating duration request for %s mins." % result)
  return flask.jsonify(success=True)


@app.route('/_updateSelectedCal', methods=['GET', 'POST'])
def _update_cal_selected():
  app.logger.debug("Got a updating cal_selected request.")
  target_info = request.get_json()
  Calendars_checked = {}
  for raw_id in target_info:
    true_id = raw_id.strip()
    Calendars_checked[true_id] = target_info[raw_id]
  app.logger.debug("Checked calendars is like" + str(Calendars_checked))
  flask.session["Checked_cals"] = Calendars_checked
  reading_user_busy_time()
  return flask.jsonify(success=True)

@app.route('/_updateSelectedUsers', methods=['GET', 'POST'])
def _updateSelectedUsers():
  app.logger.debug("Got a updating SelectedUsers request.")
  target_info = request.get_json()
  app.logger.debug("Target_info is like" + str(target_info))
  users_checked = []
  for raw_id in target_info:
    if target_info[raw_id]:
      true_id = raw_id.strip()
      users_checked.append(true_id)
  app.logger.debug("Checked user is like" + str(users_checked))
  flask.session["Checked_users"] = users_checked
  return flask.jsonify(success=True)

@app.route('/_updateUserName')
def _updateUserName():
  app.logger.debug("Got a JSON request")
  txt = flask.request.args.get("text", type=str)
  txt = "MeetingUser_" + txt
  DB.set_collection(flask.session["userid"])
  success = DB.rename_collection(txt)
  if success:
    flask.g.userid = txt
    flask.session["userid"] = txt
  rslt = {"result": success}
  return flask.jsonify(result=rslt)
#############

####
#
#  Google calendar authorization:
#      Returns us to the main /inviter screen after inserting
#      the calendar_service object in the session state.  May
#      redirect to OAuth server first, and may take multiple
#      trips through the oauth2 callback function.
#
#  Protocol for use ON EACH REQUEST:
#     First, check for valid credentials
#     If we don't have valid credentials
#         Get credentials (jump to the oauth2 protocol)
#         (redirects back to /inviter, this time with credentials)
#     If we do have valid credentials
#         Get the service object
#
#  The final result of successful authorization is a 'service'
#  object.  We use a 'service' object to actually retrieve data
#  from the Google services. Service objects are NOT serializable ---
#  we can't stash one in a cookie.  Instead, on each request we
#  get a fresh serivce object from our credentials, which are
#  serializable.
#
#  Note that after authorization we always redirect to /inviter;
#  If this is unsatisfactory, we'll need a session variable to use
#  as a 'continuation' or 'return address' to use instead.
#
####


def valid_credentials():
  """
  Returns OAuth2 credentials if we have valid
  credentials in the session.  This is a 'truthy' value.
  Return None if we don't have credentials, or if they
  have expired or are otherwise invalid.  This is a 'falsy' value. 
  """
  if 'credentials' not in flask.session:
    return None

  credentials = client.OAuth2Credentials.from_json(
      flask.session['credentials'])

  if (credentials.invalid or
          credentials.access_token_expired):
    return None
  return credentials


def get_gcal_service(credentials):
  """
  We need a Google calendar 'service' object to obtain
  list of calendars, busy times, etc.  This requires
  authorization. If authorization is already in effect,
  we'll just return with the authorization. Otherwise,
  control flow will be interrupted by authorization, and we'll
  end up redirected back to /inviter *without a service object*.
  Then the second call will succeed without additional authorization.
  """
  app.logger.debug("Entering get_gcal_service")
  http_auth = credentials.authorize(httplib2.Http())
  service = discovery.build('calendar', 'v3', http=http_auth)
  app.logger.debug("Returning service")
  return service


@app.route('/oauth2callback')
def oauth2callback():
  """
  The 'flow' has this one place to call back to.  We'll enter here
  more than once as steps in the flow are completed, and need to keep
  track of how far we've gotten. The first time we'll do the first
  step, the second time we'll skip the first step and do the second,
  and so on.
  """
  app.logger.debug("Entering oauth2callback")
  flow = client.flow_from_clientsecrets(
      CLIENT_SECRET_FILE,
      scope=SCOPES,
      redirect_uri=flask.url_for('oauth2callback', _external=True))
  # Note we are *not* redirecting above.  We are noting *where*
  # we will redirect to, which is this function.

  # The *second* time we enter here, it's a callback
  # with 'code' set in the URL parameter.  If we don't
  # see that, it must be the first time through, so we
  # need to do step 1.
  app.logger.debug("Got flow")
  if 'code' not in flask.request.args:
    app.logger.debug("Code not in flask.request.args")
    auth_uri = flow.step1_get_authorize_url()
    return flask.redirect(auth_uri)
    # This will redirect back here, but the second time through
    # we'll have the 'code' parameter set
  else:
    # It's the second time through ... we can tell because
    # we got the 'code' argument in the URL.
    app.logger.debug("Code was in flask.request.args")
    auth_code = flask.request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    flask.session['credentials'] = credentials.to_json()
    # Now I can build the service and execute the query,
    # but for the moment I'll just log it and go back to
    # the main screen
    app.logger.debug("Got credentials")
    return flask.redirect(flask.url_for('invitee'))


if __name__ == "__main__":
  # App is created above so that it will
  # exist whether this is 'main' or not
  # (e.g., if we are running under green unicorn)
  app.run(port=CONFIG.PORT, host="0.0.0.0")
