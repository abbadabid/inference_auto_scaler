minikube stop
minikube config set cpus 6
minikube config set memory 6144
minikube delete
minikube start
minikube config get cpus -- verify the num of cpus

applying the deployments

kubectl apply -f deployment.yaml
kubectl apply -f autoscaler-rbac.yaml
kubectl apply -f servicemonitor.yaml

- reinstalling the prometheus
helm install prometheus prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace


- Run in powershell to get the cpus and cores
Get-WmiObject Win32_Processor | Select-Object NumberOfCores, NumberOfLogicalProcessors

- To get the tunneling IP and port
minikube service dispatcher-service --url

- To rollout and restart deployment
kubectl rollout restart deployment autoscaler-deployment

-You don't need to reapply the deployment unless you have changed them

kubectl logs -f deployment/autoscaler-deployment -- to see the logs of auto-scaler

docker build -t abbad470/autoscaler:latest . -- to build docker image
docker push abbad470/autoscaler:latest -- to push docker image

after that rollout and restart the deployment

 kubectl scale deployment resnet-deployment --replicas=1

- minikube addons enable metrics-server -- enable the metrics server, hap needs this 

- kubectl get hpa --verify HPA is active

- kubectl delete hpa resnet-hpa -- deleting the hpa

- kubectl scale deployment resnet-deployment --replicas=1

- kubectl scale deployment autoscaler-deployment --replicas=1 -- re-enable custom autoscaler

- kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 -- port forwarding to see the results in browser




