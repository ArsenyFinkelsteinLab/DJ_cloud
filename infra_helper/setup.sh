#!/bin/bash
export SSH_KEY_PATH=$1
export ENV_FILE_PATH=$2
export IPs=$3

setup_one() {
    echo setup $IP
    ssh -i $SSH_KEY_PATH \
    -o "StrictHostKeyChecking no" \
    ubuntu@$IP \
    "sudo apt-get update && \
     sudo apt-get install -y git && \
     git clone https://gist.github.com/c6a2951519a190858c4c4ab993afc6a4.git /tmp/install_docker && \
     sudo bash /tmp/install_docker/install_docker.sh && \
     echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBXbxhK3RawvZL60ith9ZBck+5DFi/qWSZq8VgyyJ9N7 arseny_lab' >> ~/.ssh/authorized_keys"
    scp -i $SSH_KEY_PATH -o "StrictHostKeyChecking no" $ENV_FILE_PATH ubuntu@$IP:/home/ubuntu/.FinkelsteinLab.env
    
}

IFS=',' read -r -a list <<< "$IPs"
echo Setup on IPs: ${list[@]}
for IP in "${list[@]}"
do
    setup_one $SSH_KEY_PATH $IP
done

