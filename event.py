from util import base64_encode, canonical_json
import hashlib
from copy import deepcopy
import base64

def base64_encode(data, altchars="-_"):
    return base64.b64encode(data, altchars=altchars.encode("ascii")).rstrip(b"=").decode("ascii")

def get_id(event, room_version):
    # at time of writing, room_version can be 1...10
    # for future versions, this function must be updated.
    assert 1 <= room_version <= 10
    if room_version == 1 or room_version == 2:
        return event["event_id"]
    h = reference_hash(event, room_version)
    if room_version == 3:
        altchars = "+/"
    else:
        altchars = "-_"
    return "$"+base64_encode(h, altchars)


def reference_hash(event, room_version):
    # https://spec.matrix.org/v1.4/server-server-api/#calculating-the-reference-hash-for-an-event
    # 1. The event is put through the redaction algorithm.
    revent = redact(event, room_version)
    # 2. The signatures, age_ts, and unsigned properties are removed from the event, if present.
    revent.pop("signatures", None)
    revent.pop("age_ts", None)
    revent.pop("unsigned", None)
    # 3. The event is converted into Canonical JSON.
    j = canonical_json(revent)
    # 4. A sha256 hash is calculated on the resulting JSON object.
    return hashlib.sha256(j).digest()

def redact(event, room_version):
    # at time of writing, room_version can be 1...10
    # for future versions, this function must be updated.
    assert 1 <= room_version <= 10

    def filter_keys(d, allowed_keys):
        for key in list(d):
            if key not in allowed_keys:
                del d[key]
        
    revent = deepcopy(event)
    filter_keys(revent, ["event_id", "type", "room_id", "sender", "state_key", "content", "hashes", "signatures", "depth", "prev_events", "prev_state", "auth_events", "origin", "origin_server_ts", "membership"])

    allowed_content_keys = {
        # m.room.member allows key membership.
        "m.room.member": ["membership"],
        # m.room.create allows key creator.
        "m.room.create": ["creator"],
        # m.room.join_rules allows key join_rule.
        "m.room.join_rules": ["join_rule"],
        # m.room.power_levels allows keys ban, events, events_default, kick, redact, state_default, users, users_'default.
        "m.room.power_levels": ["ban", "events", "events_default", "kick", "redact", "state_default", "users", "users_default"],
        # m.room.aliases allows key aliases.
        "m.room.aliases": ["aliases"],

        # m.room.history_visibility allows key history_visibility.
        "m.room.history_visibility": ["history_visibility."],
    }

    # version 6: "All significant meaning for m.room.aliases has been removed from the redaction algorithm. The remaining rules are the same as past room versions."
    if room_version >= 6:
        allowed_content_keys.pop("m.room.aliases")

    # version 8: m.room.join_rules events now keep `allow` in addition to other keys in content when being redacted.
    if room_version >= 8:
        allowed_content_keys["m.room.join_rules"].append("allow")

    # version 9: m.room.member events now keep join_authorised_via_users_server in addition to other keys in content when being redacted.
    if room_version >= 9:
        allowed_content_keys["m.room.member"].append("join_authorised_via_users_server")

    t = revent.get("type", None)
    filter_keys(revent.get("content"), allowed_content_keys.get(t, []))

    return revent
