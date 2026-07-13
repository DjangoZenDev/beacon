# Terraform Outputs — Multi-Region Beacon
# Chapter 13: Multi-Region / Kubernetes

output "cluster_endpoints" {
  value = {
    for name, cluster in google_container_cluster.beacon :
    name => cluster.endpoint
  }
  description = "GKE cluster API endpoints per region"
}

output "cockroachdb_ips" {
  value = {
    for name, instance in google_compute_instance.cockroachdb :
    name => instance.network_interface[0].access_config[0].nat_ip
  }
  description = "CockroachDB node public IPs per region"
}

output "redis_hosts" {
  value = {
    for name, instance in google_redis_instance.beacon_cache :
    name => instance.host
  }
  description = "Redis Memorystore hostnames per region"
}
