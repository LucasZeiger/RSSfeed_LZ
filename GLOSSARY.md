# NewsLens

NewsLens compares coverage of news events and explains possible financial exposure while keeping evidence and interpretation distinct.

## Language

**Article**:
A publisher's individual news item, retaining its original headline, attribution, link and available feed excerpt.

**Story**:
A group of articles believed to report the same event. Membership expresses a judgement about event similarity, not a guarantee that the accounts agree.
_Avoid_: Topic

**Political leaning**:
A configured publisher classification of left, centre, right or unknown, interpreted in its country's political context and accompanied by its rationale and review provenance. It is not a judgement about an individual article's truthfulness.

**Coverage distribution**:
The share of collected articles or distinct publishers in each political category. It describes the configured source set, not the entire media landscape.

**Framing**:
The wording, emphasis and interpretation in the available reporting of an event. Differences in framing do not by themselves establish dishonesty.

**Potential exposure**:
A plausible economic mechanism connecting an event to a sector or financial instrument, with supporting evidence and uncertainty.
_Avoid_: Trading signal, price prediction

**Observed market movement**:
A measured historical price change over a stated period. Its proximity to a news event does not establish causation.

**Demo dataset**:
Explicitly labelled synthetic news and market information used to demonstrate NewsLens without external credentials.

**Live dataset**:
NewsLens information derived from real feed material, with any market prices drawn from a configured provider. "Live" distinguishes real from synthetic information; it does not imply real-time updates.

**Watchlist**:
The configured set of financial instruments for which NewsLens provides relevant news and available market context. Inclusion does not imply ownership or a recommendation.
_Avoid_: Portfolio
