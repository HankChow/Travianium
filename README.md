# Travianium

Operating Travian via Python


### Background

Travian is a web game I used to play more tha n ten years ago. It spends lots of time for executing accurate operations. I am now trying to make it simpler in operating. Since the webpages of this game is rendered at the server side, I have to parse the webpages in order to get all the information I need.


### Dependencies

* Python 3.8+
* requests
* bs4


### Usage

#### Environment Variables

Personal credentials are not stored in the code or certain files. They should be set in the environment variables so that they can be read safely. 

Currently used environment variables are shown below:

* `tr_username`: the username for logging in to Travian
* `tr_password`: the password for logging in to Travian
* `tr_server`: the hostname of the Travian server, for example `gos.x1.international.travian.com`


### Done

* getting information
  * warehouse and granary
  * production
  * troops and movements
  * level of resource fields and buildings
  * building list
  * maps
  * hero
* actions
  * upgrading resource fields and buildings


### To do

* bugfix
  * not displaying correctly when there are both incoming and outgoing movements
  * building status of stone wall
* getting information
  * villages
* actions
  * producing troops
  * sending troops
* code
  * assertion for avoiding page structure changing


