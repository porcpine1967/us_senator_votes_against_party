        ---
title: "Calculations of Senators Voting against Majority of Party"
author: "Jeffrey Dettmann"
date: "February 7, 2016"
---

The code available in this repository calculates the number of times each United States Senator voted against the majority of his or her party and the impact of these votes.

## Notes:
1. This code was developed against python 2.7.6 and requires the external pyyaml module. `sudo pip install pyyaml`
2. This code automatically downloads data from www.senate.gov.
3. This code uses the word 'betrayal' to indicate a vote by a Senator against the majority of his or her own party that led to the failure of the majority of the party to imprint its will on the result. It is not meant pejoratively, but is rather used because it is much shorter than any other way of describing the event.

## Instructions
1. Clone this repository into a directory we will henceforth refer to as "the working directory".
2. Load senator data: `python calculate.py na --action load-senators`
3. Run the code in the working directory from the command line: `python calcluate.py 1989-2015`

Note: when running the first time, the code downloads yearly data, builds the domain objects, and pickles them in the appropriate directory. After the first run, the code should run much faster.

### Input
* First position (years)
  * The years the program should work with
  * CSV: years can be given in csv with no spaces: `1999,2001,2007`
  * Range: years can be given in a range: `1989-2015`
* --action
  * Valid values: load-senators, load-years, calculate (default)
  * load-senators: rsyncs information on senators, builds Senator domain objects, and saves them in legislators.pickle. The years argument is not used.
  * load-years: for each year given in the positional argument, rsync data for that year, build Tally domain objects, and save them in {year}/tallies.pickle
  * calculate: analyse the data as described in the CodeBook and print out results. It will rsync and pickle data if it has not been pre-loaded.
* --only-current: after calculation, only print information on current senators
* --only-necessary: make calculations based on tallies in which a betrayal is necessary by methods described in the CodeBook
* --limit: only print the results from this number of senators; default is 20, use 0 for all
* --only-pc: only print out information on senators who were running for president as of February 7, 2016
* --sort
  * Attribute of values to sort by (descending)
  * Valid values: all, total, success, fail, pct as described in CodeBook

## Known Issues
* Data before 1989 is not parsable, as it indicates the result of a tally in a different field
* Data before 1941 is not stored by year, but rather by session and a cardinal number, and this code cannot handle that
* Determinants of success or failure of a roll call is based on string matching. Addition of more years will probably lead to strings that need to be added to one list or the other.
