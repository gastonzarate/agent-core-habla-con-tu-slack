from dataclasses import dataclass


def embedding_model_arn(region: str) -> str:
    return f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"


@dataclass(frozen=True)
class Config:
    region: str
    prefix: str
    vector_bucket: str
    vector_index: str
    kb_name: str
    embedding_model_arn: str
    embedding_dim: int = 1024


def load_config(region: str = "us-west-2", prefix: str = "slackrag") -> Config:
    return Config(
        region=region,
        prefix=prefix,
        vector_bucket=f"{prefix}-vectors",
        vector_index=f"{prefix}-index",
        kb_name=f"{prefix}-kb",
        embedding_model_arn=embedding_model_arn(region),
    )
