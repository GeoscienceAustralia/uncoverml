#!/bin/bash 
#PBS -N uncoverml
#PBS -P ge3 
#PBS -q gpuvolta
#PBS -l walltime=24:00:00
#PBS -l ncpus=12
#PBS -l ngpus=1
#PBS -l mem=96GB
#PBS -l jobfs=100GB
#PBS -l storage=gdata/ge3 
module purge
module load pbs
module load python3/3.7.4
module load gdal/3.0.2

set -e
ulimit -s unlimited

GIT_HOME=$HOME/github  # where to check out the uncover-ml repoitory
VENVS=$HOME/venvs

# activate the virtual env you have created
source $VENVS/uncoverml_gadi/bin/activate

PBS_WORKDIR=$GIT_HOME/uncover-ml
cd $PBS_WORKDIR

export jport=8388  # choose a port number

echo "Starting Jupyter lab ..."
jupyter lab --no-browser --ip=`hostname` --port=${jport} &


echo "ssh -N -L ${jport}:`hostname`:${jport} ${USER}@gadi.nci.org.au &" > client_cmd
echo "client_cmd created ..."

sleep infinity 
