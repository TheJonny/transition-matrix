import requests
import json
import nacl.signing
import binascii
import urllib.parse
from util import canonical_json

def authorization_headers(origin_name, origin_signing_key,
                          destination_name, request_method, request_target,
                          content=None):
    request_json = {
         "method": request_method,
         "uri": request_target,
         "origin": origin_name,
         "destination": destination_name,
    }

    if content is not None:
        # Assuming content is already parsed as JSON
        request_json["content"] = content

    signed_json = sign_json(request_json, origin_signing_key, origin_name)

    authorization_headers = []

    for key, sig in signed_json["signatures"][origin_name].items():
        authorization_headers.append(
                "X-Matrix origin=\"%s\",destination=\"%s\",key=\"%s\",sig=\"%s\"" % (
                    origin_name, destination_name, key, sig,
                    )
                )

    return {"Authorization": authorization_headers[0]}



def sign_json(json_object, signing_key, signing_name):
    signatures = json_object.pop("signatures", {})
    unsigned = json_object.pop("unsigned", None)

    signed = signing_key.sign(canonical_json(json_object))
    signature_base64 = binascii.b2a_base64(signed.signature).strip().strip(b"=").decode()

    key_id = "%s:%s" % (signing_key.alg, signing_key.version)
    signatures.setdefault(signing_name, {})[key_id] = signature_base64

    json_object["signatures"] = signatures
    if unsigned is not None:
        json_object["unsigned"] = unsigned

    return json_object

class FederationClient:
    def __init__(self, server_name, signing_key):
        self.server_name = server_name
        alg, key_version, kb64 = signing_key.split()
        assert alg == "ed25519"
        self.signing_key = nacl.signing.SigningKey(binascii.a2b_base64(kb64 + "="))
        self.signing_key.alg = alg
        self.signing_key.version = key_version
        self.session = requests.Session()

    def request(self, destination, method, endpoint, query=None, content=None, homeserver=None):
        target = endpoint
        if query is not None:
            target += "?" + urllib.parse.urlencode(query, True)
        h = authorization_headers(self.server_name, self.signing_key, destination, method, target, content)
        print(f"{method} {homeserver+target}")
        r = self.session.request(method, homeserver + target, data=content, headers=h)
        #print(r.text)
        r.raise_for_status()
        return r.json()

if __name__ == "__main__":
    import config
    c = FederationClient(config.domain, config.signing_key)
    r = c.request("bruckbu.de", "GET", "/_matrix/federation/v1/backfill/" + urllib.parse.quote("!SMloEYlhCiqKwRLAgY:fachschaften.org"), query=dict(v=[], limit=50), homeserver=config.homeserver)
    print(json.dumps(r))
