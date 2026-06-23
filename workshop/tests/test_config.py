from config import load_config, embedding_model_arn


def test_embedding_model_arn_uses_region():
    arn = embedding_model_arn("us-west-2")
    assert arn == "arn:aws:bedrock:us-west-2::foundation-model/amazon.titan-embed-text-v2:0"


def test_load_config_defaults():
    cfg = load_config(region="us-west-2", prefix="slackrag")
    assert cfg.region == "us-west-2"
    assert cfg.vector_bucket == "slackrag-vectors"
    assert cfg.vector_index == "slackrag-index"
    assert cfg.kb_name == "slackrag-kb"
    assert cfg.embedding_dim == 1024
    assert cfg.embedding_model_arn.endswith("amazon.titan-embed-text-v2:0")
