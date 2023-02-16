#!/bin/bash
export WORKFLOW_NAME=$1
docker ps -a --format '{{.Names}}'
mkdir -p /tmp/${WORKFLOW_NAME}_Log && docker ps -a --format '{{.Names}}' | xargs -I {} bash -c "docker logs {} > /tmp/${WORKFLOW_NAME}_Log/{}-$(date '+%Y%m%d-%H%M%S').log 2>&1"
