Synthetic webhook payloads for acme/shop#7 (the fixture in ../acme_shop_pr7), shaped
like GitHub's documented `pull_request_review_thread`, `check_run` and `check_suite` events.
`check_suite_rerequested.json` is the shape GitHub sends when "Re-run" is pressed on an app's
check in the pull-request UI (found in the first live run; the suite is on an older commit). Only the
fields VeriReview reads are present. `thread_resolved.json` carries a prompt-injection text,
a link and an @-mention in the comment body on purpose: advisory mode must ignore them.
