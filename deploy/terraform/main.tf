terraform {
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}
# Minimal container deploy. Swap the provider block for aws_ecs_service,
# azurerm_container_app, or google_cloud_run_v2_service as needed.
provider "docker" {}
resource "docker_image" "consentledger" { name = "ghcr.io/cognis-digital/consentledger:latest" }
resource "docker_container" "consentledger" {
  name  = "consentledger"
  image = docker_image.consentledger.image_id
  ports { internal = 8000 external = 8000 }
}
