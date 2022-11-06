def base64_encode(data, altchars="-_"):
    return base64.b64encode(data, altchars=altchars.encode("ascii")).rstrip(b"=").decode("ascii")


def canonical_json(value):
    import json
    return json.dumps(
        value,
        # Encode code-points outside of ASCII as UTF-8 rather than \u escapes
        ensure_ascii=False,
        # Remove unnecessary white space.
        separators=(',',':'),
        # Sort the keys of dictionaries.
        sort_keys=True,
        # Encode the resulting Unicode as UTF-8 bytes.
    ).encode("UTF-8")
