Synthetic webhook payloads for acme/shop#7 (the fixture in ../acme_shop_pr7), shaped
like GitHub's documented `pull_request_review_thread` and `check_run` events. Only the
fields VeriReview reads are present. `thread_resolved.json` carries a prompt-injection text,
a link and an @-mention in the comment body on purpose: advisory mode must ignore them.
