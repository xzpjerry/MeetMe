#
#  Project 7: Pull Google calendar events 

##############
#  Virtual environment


# Many recipes need to be run in the virtual environment, 
# so run them as $(INVENV) command
INVENV = . env/bin/activate ;

install: env

env:
	python3 -m venv env
	$(INVENV) pip3 install -r requirements.txt

# 'make run' runs Flask's built-in test server, 
#  with debugging turned on unless it is unset in CONFIG.py
# 
credentials:  meetings/credentials.ini

meetings/credentials.ini:
	echo "You just install the database and credentials.ini for it"

run:	env
	($(INVENV) cd meetings; python3 flask_main.py) ||  true

test:	env
	$(INVENV) cd meetings; nosetests

start:	env credentials
	bash start.sh

stop:	env credentials
	bash stop.sh


##
## Preserve virtual environment for git repository
## to duplicate it on other targets
##
dist:	env
	$(INVENV) pip freeze >requirements.txt


# 'clean' and 'veryclean' are typically used before checking 
# things into git.  'clean' should leave the project ready to 
# run, while 'veryclean' may leave project in a state that 
# requires re-running installation and configuration steps
# 
clean:
	rm -f *.pyc */*.pyc
	rm -rf __pycache__ */__pycache__

veryclean:
	make clean
	rm -rf env



