"""
Confidence Model - v3.0 置信度计算
基于: 来源节点权威度 × 时效性系数 × 交叉验证系数
"""
import math
from datetime import datetime
from typing import Optional


class ConfidenceModel:
    """
    置信度模型
    单条置信度 = 来源节点权威度 × 时效性系数 × 交叉验证系数
    """

    # 节点权威度默认值
    DEFAULT_AUTHORITY = 0.5
    AUTHORITY_RANGE = (0.1, 1.0)

    # 仲裁后调整幅度
    WIN_AUTHORITY_BOOST = 0.1
    LOSE_AUTHORITY_PENALTY = 0.05

    # 时效性衰减参数
    LAMBDA = 0.001  # 每天衰减

    AUTHORITY_DB_PATH = os.path.expanduser("~/.misakanet/authority_db.json")

    def __init__(self, authority_db: dict = None, db_path: str = None):
        """
        authority_db: {node_id: authority_score} 节点权威度字典
        db_path: 持久化路径，默认 ~/.misakanet/authority_db.json
        """
        if db_path:
            self.AUTHORITY_DB_PATH = db_path
        self.authority_db = authority_db or {}
        self._load_from_disk() if not authority_db else None

    def _load_from_disk(self):
        """从磁盘加载权威度数据"""
        import json
        try:
            with open(self.AUTHORITY_DB_PATH, 'r') as f:
                self.authority_db = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.authority_db = {}

    def _save_to_disk(self):
        """持久化权威度数据到磁盘"""
        import json, os
        os.makedirs(os.path.dirname(self.AUTHORITY_DB_PATH), exist_ok=True)
        with open(self.AUTHORITY_DB_PATH, 'w') as f:
            json.dump(self.authority_db, f, indent=2)

    def get_authority(self, node_id: str) -> float:
        """获取节点权威度"""
        return self.authority_db.get(node_id, self.DEFAULT_AUTHORITY)

    def set_authority(self, node_id: str, authority: float):
        """设置节点权威度（仲裁后调用）"""
        authority = max(self.AUTHORITY_RANGE[0],
                      min(self.AUTHORITY_RANGE[1], authority))
        self.authority_db[node_id] = authority
        self._save_to_disk()

    def update_after_arbitration(self, winner_id: str, loser_ids: list):
        """仲裁后更新权威度"""
        # 胜出方 +0.1
        current = self.get_authority(winner_id)
        self.set_authority(winner_id, current + self.WIN_AUTHORITY_BOOST)

        # 失败方 -0.05
        for loser_id in loser_ids:
            current = self.get_authority(loser_id)
            self.set_authority(loser_id, current - self.LOSE_AUTHORITY_PENALTY)

    def calc_time_factor(self, indexed_at: str) -> float:
        """
        计算时效性系数
        e^(-λt)，λ=0.001/天
        """
        try:
            indexed_time = datetime.fromisoformat(indexed_at)
            age_days = (datetime.now() - indexed_time).total_seconds() / 86400
            return math.exp(-self.LAMBDA * age_days)
        except (ValueError, TypeError):
            return 1.0  # 无法解析时默认满分

    def calc_cross_factor(self, source_count: int) -> float:
        """
        计算交叉验证系数
        1节点=0.8，2节点=0.95，3节点+=1.0
        """
        if source_count <= 0:
            return 0.8
        elif source_count == 1:
            return 0.8
        elif source_count == 2:
            return 0.95
        else:
            return 1.0

    def calc_confidence(self, skill: dict) -> float:
        """
        计算单条 Skill 的置信度
        """
        # 来源节点权威度
        source = skill.get("source", "unknown")
        if isinstance(source, list):
            source = source[0] if source else "unknown"
        authority = self.get_authority(source)

        # 时效性系数
        indexed_at = skill.get("indexed_at", "")
        time_factor = self.calc_time_factor(indexed_at)

        # 交叉验证系数
        sources = skill.get("sources", [source])
        if not isinstance(sources, list):
            sources = [sources]
        cross_factor = self.calc_cross_factor(len(sources))

        # 综合计算
        confidence = authority * time_factor * cross_factor
        return round(min(1.0, confidence), 4)

    def calc_confidence_for_versions(self, versions: list) -> list:
        """为多个版本计算置信度"""
        return [
            {**v, "confidence": self.calc_confidence(v)}
            for v in versions
        ]
