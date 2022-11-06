import requests
import json
from pprint import pprint
import config
import urllib
import dbm.gnu

from util import canonical_json
import event


from federation import FederationClient
from heapq import heapify, heappush, heappop

ses = requests.Session()

class Client:
    def __init__(self, homeserver, uid, access_token, logout_on_exit=True):
        assert uid is None or uid.startswith("@")
        self.homeserver = homeserver
        self.uid = uid
        self.headers = {"Authorization": "Bearer " + access_token}
        self.access_token = access_token
        self.session = requests.Session()
        self.logout_on_exit = logout_on_exit

    def request(self, method, endpoint, query={}, data=None, json=True, raise_for_status=True):
        response = self.session.request(method, self.homeserver + endpoint,
                                        params=query, data=data, headers=self.headers)
        if raise_for_status:
            response.raise_for_status()
        if json:
            return response.json()
        else:
            return response.content
    def logout(self):
        self.request("POST", "/_matrix/client/v3/logout")
    def get_profile(self):
        return self.request("GET", "/_matrix/client/v3/profile/" + self.uid)
    def __enter__(self):
        return self
    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        if self.logout_on_exit and "Authorization" in self.headers:
            self.logout()
        return False
    def get_account_data(self):
        """ similiar to GET /_synapse/admin/v1/users/<user_id>/accountdata, but using a sync request"""
        no_events = {"limit": 0, "types": []}
        room_only_account_data = {
                # "account_data": All
                "ephemeral": no_events,
                "timeline": no_events,
                "state": no_events,
                }
        sync_filter = {
                # no filter on the account_data, we want all.
                # "account_data": {},
                # "event_fields": [...]
                # [string]    List of event fields to include. If this list is absent then all fields are included.

                #    enum    The format to use for events. ‘client’ will return the events in a format suitable for clients. ‘federation’ will return the raw event as received over federation. The default is ‘client’.
                "event_format": "client",

                "presence": no_events, #    EventFilter     The presence updates to include.
                "room": room_only_account_data,
                }
        query = {
                "set_presence": "offline",
                "filter": json.dumps(sync_filter),
                }
        sync_response = self.request("GET", "/_matrix/client/v3/sync", query=query)
        res = {}
        res["global"] = sync_response["account_data"]
        res["rooms"] = {}
        for room, data in sync_response["rooms"]["join"].items():
            res["rooms"][room] = data["account_data"]["events"]
        return res
    def get_devices(self):
        devices_response = self.request("GET", "/_matrix/client/v3/devices")
        return devices_response["devices"]
    def get_pushers(self):
        pushers_response = self.request("GET", "/_matrix/client/v3/pushers")
        return pushers_response["pushers"]

    def dump_user(self):
        res = {
            "uid": self.uid,
            "profile": self.get_profile(),
            "account_data": self.get_account_data(),
            "devices": self.get_devices(),
            "pushers": self.get_pushers(),
        }
        return res

class SynapseAdminClient(Client):
    def iter_users(self):
        total = 1
        n = 0
        params = {
            "limit": 100,
            "guests": "false",
        }
        while n < total:
            response = self.request("GET", "/_synapse/admin/v2/users", query=params)
            n += len(response["users"])
            yield from response["users"]
            total = response["total"]
            if n < total:
                params["from"] = response["next_token"]
    def iter_messages(self, room):
        params = dict(dir="b", limit=100)
        while True:
            rr = self.request("GET", "/_synapse/admin/v1/rooms/"+urllib.parse.quote(room)+"/messages", query=params)
            yield from rr["chunk"]
            if "end" in rr:
                params["from"] = rr["end"]
            else:
                break

    def impersonate(self, uid):
        # ugly workaround as synapse does not allow to impersonate oneself
        if uid == self.uid:
            return Client(self.homeserver, uid, self.access_token, logout_on_exit=False)
        token = self.request("POST", "/_synapse/admin/v1/users/" + uid + "/login")["access_token"]
        return Client(self.homeserver, uid, token)





a = SynapseAdminClient(config.homeserver, config.uid, config.token)

room = "!SMloEYlhCiqKwRLAgY:fachschaften.org" # #conduit

unknown_events = []
print("getting messages via admin API:")
for i,m in enumerate(a.iter_messages(room)):
    print(i, m["event_id"])
    unknown_events.append((-m["origin_server_ts"], m["event_id"]))



fc = FederationClient(config.domain, config.signing_key)

# leach all events using synapse api + backfill (to get the DAG)

# priority queue with older timestamps first, to avoid gaps
# the timestamp will come from the referencing event, but initially we use the
# own timestamp.

heapify(unknown_events)

print(rr["chunk"])
known_events = set()

print(unknown_events)
nerrors = 0

evdb = dbm.gnu.open("events_by_id.db", "c")

while unknown_events:
    (_, e) = heappop(unknown_events)
    if e in known_events: continue
    print("popped from", len(unknown_events)+1, "unknown events")
    try:
        t = fc.request(config.domain, "GET", "/_matrix/federation/v1/backfill/"+urllib.parse.quote(room), query=dict(v=e, limit=100), homeserver=config.homeserver)
    except requests.exceptions.HTTPError as e:
        print(e)
        nerrors += 1
        print(nerrors, "errors")
        known_events.add(e)
        continue

    found_e = False
    for evt in t["pdus"]:
        eid = event.get_id(evt, 6)
        if eid == e:
            found_e = True
        if eid in known_events:
            continue
        known_events.add(eid)
        
        evdb[eid.encode()] = canonical_json(evt)

        for p in evt["prev_events"] + evt["auth_events"]:
            if p in known_events: continue
            heappush(unknown_events, (-evt["origin_server_ts"], p))
    if not found_e:
        print("Missing:", e)
        nerrors += 1

    print(f"{nerrors = }")
    print(f"{len(known_events) - nerrors =}")
    if len(known_events) == 1000:
        break

#pprint(a.dump_user())

##whatsapp = telegram = signal = n = 0


##for u in a.iter_users():
##    n += 1
##    uid = u["name"]
##    if u["name"].startswith("@telegram_"):
##        telegram += 1
##        continue
##    if u["name"].startswith("@whatsapp_"):
##        whatsapp += 1
##        continue
##    if u["name"].startswith("@signal_"):
##        signal += 1
##        continue
##    print(u["name"])
##    account_data = a.request("GET", "/_synapse/admin/v1/users/"+uid+"/accountdata")
##    pprint(account_data)
##    #with a.impersonate(u["name"]) as puppet:
##    #    pprint(puppet.profile())
##
##
##print(f"{telegram=}")
##print(f"{whatsapp=}")
##print(f"{signal=}")
##print(f"{n=}")

#with a.impersonate("@thejonny:bruckbu.de") as puppet:
