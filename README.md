# transition-matrix - a change of basis for your chat
## Migration tool for matrix servers

At the moment, this is unfinished, experimental software for breaking my personal server.
But in the long run, (contributing to) a universal matrix server 

Sorry, but following the convention we have to use math names to protest against search engine optimisation.

### Approach
I want to migrate from `synapse` to `conduit`.

- Dump all users
  - enumerate by `/_synapse/admin` API and get login tokens for them
  - dumping could also be done by admin API, but to improve future portability, we use `/_matrix/client`.
  - one json file per user, containing
    - `uid`: user id
    - `profile` consiting of  `displayname` and `avatar`
    - `account_data`: `global` and by `room` in the format described in the synapse admin api, implemented with a `sync`. This contains all the E2EE public keys and the key backup
    - `devices`
    - `pushers`
  - maybe a password hash and/or thirdparty ids for password resets
  - no login tokens, devices should be able to log in with the same device id after a soft logout.

- Dump Room state (via admin api) and it's auth chain (via federation requests to `.../event/...`). Synapse can talk happily to "itself", i.e. using the own domain name and signing key for the requests.
  - will be a json file per room
  - in later state resolutions, conduit will fetch the other state events via federation
- Transfer signing key

- import user and room state into a conduit database
- implement backfilling in conduit
  - patch it so it can request from the own domain by connecting to the synapse instance


- tell users to scroll through their rooms that have no users on other servers (or automate it using `_matrix/client/messages` requests)
  - i think for me that's mostly private chat or bridged rooms.

- what am I missing? :)

