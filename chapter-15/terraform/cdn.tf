# Terraform — CloudFront CDN + S3 Static Website
# Chapter 15: The Cost of Scale
# CloudFront distribution in front of S3 for static/media assets.
# Reduces origin load and improves global latency.

resource "aws_cloudfront_distribution" "beacon_cdn" {
  enabled = true
  comment = "Beacon static/media CDN (Ch15)"

  origin {
    domain_name = aws_s3_bucket.beacon_static.bucket_regional_domain_name
    origin_id   = "S3-beacon-static"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.beacon_oai.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-beacon-static"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true  # Reduce egress costs by 60-80%.

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 86400    # 24 hours
    max_ttl     = 31536000  # 1 year
  }

  price_class = "PriceClass_100"  # NA + EU only, save 30% vs all edge.

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Name = "beacon-cdn", Chapter = "15" }
}

# S3 bucket for static/media assets with static website hosting.
resource "aws_s3_bucket" "beacon_static" {
  bucket = "beacon-static-${var.project_id}"
}

resource "aws_s3_bucket_website_configuration" "beacon_static_website" {
  bucket = aws_s3_bucket.beacon_static.id
  index_document { suffix = "index.html" }
  error_document { key = "error.html" }
}

resource "aws_s3_bucket_public_access_block" "beacon_static_block" {
  bucket                  = aws_s3_bucket.beacon_static.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_identity" "beacon_oai" {
  comment = "Beacon OAI for S3 static bucket"
}

# S3 bucket policy — only CloudFront can read.
data "aws_iam_policy_document" "beacon_static_policy" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.beacon_static.arn}/*"]
    principals {
      type        = "AWS"
      identifiers = [aws_cloudfront_origin_access_identity.beacon_oai.iam_arn]
    }
  }
}

resource "aws_s3_bucket_policy" "beacon_static_policy_attach" {
  bucket = aws_s3_bucket.beacon_static.id
  policy = data.aws_iam_policy_document.beacon_static_policy.json
}
