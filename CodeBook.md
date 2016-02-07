---
title: "Calculations of Senators Voting against Majority of Party"
author: "Jeffrey Dettmann"
date: "February 7, 2016"
---
The data used in this product is from [govtrack](https://www.govtrack.us/developers). Format of the voting data is available here: [https://github.com/unitedstates/congress/wiki/votes](https://github.com/unitedstates/congress/wiki/votes).

## Definitions
For all calculations, only 'yea', 'nay', 'guilty', and 'not guilty' votes are considered. Votes of 'present' and 'not voting' are simply ignored.

### Success
Voting in a way that supports the final resolution of the roll call. For example, on a bill, if a Senator voted 'yea' and the bill passed it would be a success, but if the Sentator voted 'nay' and the bill passed it would not be a success. Success is not the same as majority, as some roll calls require three-fifths or even two-thirds to pass. In one case, the majority of both Democrats and Republicans voted 'aye' yet the roll call failed, as it required two-thirds support, which it did not receive.

### The will of the party
For each roll call, the code calculates the percentage of the party that voted yea and nay (ignoring other votes); thus yeas/(yeas + nays) and nays/(yeas + nays). The will of the majority is any percentage > 50. In preliminary analysis, no votes appeared with an even split in a given party.

### Voting against the will of the party
Any vote in which less than 50% of fellow party members voted similarly.

### Betrayal
A vote against the will of the party in which the vote acheived its objective. Despite its connotation, I do not mean this term pejoratively, but merely as the simplest way to describe this condition.

### Futile Betrayal
Voting against the will of the party when the will of the party succeeded.

### Betrayal Necessary
A roll call which would not have led to the same resolution had the betrayals not voted. So in a simple majority vote, if there were 40 ayes and 38 nays, and 3 of the ayes were betrayals, the betrayal was considered necessary. Other methods of calculation, such as making calculations based on switching vote rather than simply not voting, were considered too complicated without adding sufficient value to the model. Similarly, I allow ties to go to the 'nays' as an arbitrary simplification.

## Output

### Columns
1. All: all of the votes made by this Senator in the years under calculation. This value is not used in any subsequent calculation but is offered for scale.
1. Total: Number of times the Senator voted against the will of the party in the years under calculation.
1. Successful: Number of times the Senator voted against the will of the party and the roll call resolved in the manner the Senator voted in the years under calculation.
1. Success Pct: Number of successful votes against the will of the party divided by all the votes against the will of the party in the years under calculation.
1. Senator: The name, party, and state of the Senator. If the Senator belonged to more than one party or represented more than one state in the years under calculation, all are listed.

### Sorting
Note: all reports return data in descending order

* all: Order by number of votes made by the Senator in the years under calculation
* total: Order by the number of votes against the will of the party made by the Senator in the years under calculation
* success: Order by the number of votes against the will of the party in which the Senator succeeded in the years under calculation
* fail: Order by the number of votes against the will of the party in which the Senator failed in the years under calculation (no column)
* pct: Order by the number of votes against the will of the party in which the Senator succeeded divided by total votes against the will of the party in the years under calculation
