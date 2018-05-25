publish:
	pip install -r requirements.txt
	python setup.py install
	rm -rf build dist *.egg-info

clean:
	rm -rf build dist *.egg-info
