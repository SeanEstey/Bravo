import csv
import urllib2

numbers = urllib2.urlopen('http://23.239.21.165/calls.csv')
reader = csv.reader(numbers)
for row in reader:
    print 'Name: ' + row[0]
    print 'Date: ' + row[1]
    print 'Phone: ' + row[2]


