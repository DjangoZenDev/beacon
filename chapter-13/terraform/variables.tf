# Terraform Variables — Multi-Region Beacon
# Chapter 13: Multi-Region / Kubernetes

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "beacon-production"
}

variable "primary_region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-east1"
}

variable "cluster_name" {
  description = "Base name for GKE clusters"
  type        = string
  default     = "beacon"
}

variable "regions" {
  description = "Multi-region deployment configuration"
  type = map(object({
    location = string
  }))
  default = {
    "us-east"  = { location = "us-east1" }
    "eu-west"  = { location = "europe-west1" }
    "ap-south" = { location = "asia-south1" }
  }
}

variable "cockroachdb_nodes" {
  description = "Number of CockroachDB nodes per region"
  type        = number
  default     = 3
}

variable "redis_memory_gb" {
  description = "Redis Memorystore capacity per region (GB)"
  type        = number
  default     = 4
}
