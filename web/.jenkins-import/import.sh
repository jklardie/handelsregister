#!/bin/bash

set -e
set -u

DIR="$(dirname $0)"

dc() {
	docker-compose -p hr -f ${DIR}/docker-compose.yml $*;
}

dc pull

trap 'dc kill ; dc rm -f -v' EXIT

echo "Do we have OS password?"
echo $HANDELSREGISTER_OBJECTSTORE_PASSWORD
echo "Do we have ENVIRONMENT?"
echo $ENVIRONMENT

rm -rf ${DIR}/backups
mkdir -p ${DIR}/backups

dc build --pull

dc up -d database

# wait to give postgres the change to be up
sleep 50

# load latest bag into database
echo "Load latest verblijfsobjecten, ligplaatsen, standplaatsen and nummeraanduidingen in handelsregister database"

# First delete (possibly empty) dump for bag
dc exec -T database rm -f /tmp/bag_latest.gz
dc exec -T database update-table.sh bag bag_verblijfsobject public handelsregister
dc exec -T database update-table.sh bag bag_ligplaats public handelsregister
dc exec -T database update-table.sh bag bag_standplaats public handelsregister
dc exec -T database update-table.sh bag bag_nummeraanduiding public handelsregister

echo "create hr api database / reset elastic index"
# create the hr_data and reset elastic
dc run --rm importer

echo "DONE! importing mks into database"

echo "create hr dump"
# run the backup shizzle
dc run --rm db-backup

echo "create hr index"
dc up importer_el1 importer_el2 importer_el3

# wait until all building is done
import_status=`docker wait hr_importer_el1_1 hr_importer_el2_1 hr_importer_el3_1`

# count the errors.
import_error=`echo $import_status | grep -o "1" | wc -l`

echo $import_error

if (( $import_error > 0 ))
then
    echo 'Elastic Import Error. 1 or more workers failed'
    exit 1
fi

dc run --rm el-backup

echo "DONE! with Import! You are awesome! <3"
