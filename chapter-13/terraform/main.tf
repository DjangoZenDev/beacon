# Terraform — Multi-Region Beacon Infrastructure
# Chapter 13: Multi-Region / Kubernetes
# Provisions GKE/EKS clusters in 3 regions, CockroachDB, Redis, Kafka.
# Principle 17: "Autonomous degradation beats central coordination."

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.primary_region
}

# ── GKE Clusters ────────────────────────────────────────────
resource "google_container_cluster" "beacon" {
  for_each = var.regions
  name     = "beacon-${each.key}"
  location = each.value.location

  initial_node_count = 3
  remove_default_node_pool = true

  node_config {
    machine_type = "e2-standard-4"
    disk_size_gb = 100
    labels = {
      region = each.key
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

# ── CockroachDB ──────────────────────────────────────────────
resource "google_compute_instance" "cockroachdb" {
  for_each     = var.regions
  name         = "cockroachdb-${each.key}-${count.index}"
  count        = 3
  machine_type = "n2-standard-4"
  zone         = "${each.value.location}-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-2204-lts"
      size  = 200
    }
  }

  labels = {
    region  = each.key
    service = "cockroachdb"
  }

  metadata_startup_script = <<-EOT
    # CockroachDB startup — node joins the multi-region cluster
    cockroach start --insecure \
      --join=cockroachdb-us-east-0,cockroachdb-eu-west-0,cockroachdb-ap-south-0 \
      --locality=region=${each.key} \
      --cache=25% --max-sql-memory=25%
  EOT
}

# ── Redis (Memorystore) ──────────────────────────────────────
resource "google_redis_instance" "beacon_cache" {
  for_each       = var.regions
  name           = "beacon-redis-${each.key}"
  memory_size_gb = 4
  tier           = "STANDARD_HA"
  region         = each.value.location
}

# ── Outputs ──────────────────────────────────────────────────
output "cluster_endpoints" {
  value = {
    for name, cluster in google_container_cluster.beacon :
    name => cluster.endpoint
  }
  description = "GKE cluster API endpoints per region"
}
