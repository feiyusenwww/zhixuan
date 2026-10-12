"""后端接口契约冒烟测试。

断言 OpenAPI 暴露的路径与 docs/api-contract.md 完全一致，防止契约漂移。

无需 pytest，直接运行：
    cd backend && .venv\\Scripts\\python.exe test_routes.py

说明：FastAPI 0.143 起 app.routes 不再拍平被 include 的子路由，
因此这里改用 app.openapi()，与框架版本无关，并顺带验证 OpenAPI 可用（tasks.md 1.5）。

注意：下面带 NEW 标记的接口为新增，契约 docs/api-contract.md 尚未收录，
已在 PR 描述中提请队长补入。契约合并后请删除标记与本节说明。
"""

from __future__ import annotations

from app.main import app

EXPECTED = {
    ("/api/health", "get"),
    ("/api/auth/register", "post"),
    ("/api/auth/login", "post"),
    ("/api/user/profile", "get"),
    ("/api/user/profile", "put"),
    ("/api/pathways", "get"),
    ("/api/pathways/eligibility-check", "post"),
    ("/api/qa", "get"),
    ("/api/plans", "post"),
    ("/api/schools", "get"),
    # NEW：新增接口，待补入契约（途径详情 4.1、区域判定 4.3）
    ("/api/pathways/region-check", "get"),
    ("/api/pathways/{pathway_id}", "get"),
    # NEW：新增接口，待补入契约（认证 3.1/3.3）
    ("/api/auth/logout", "post"),
    ("/api/auth/me", "get"),
    ("/api/user", "delete"),
    # NEW：新增接口，待补入契约（方案保存/命名/编辑，产品书 6.1.7、tasks.md 6.6）
    ("/api/user/plans", "get"),
    ("/api/user/plans", "post"),
    ("/api/user/plans/{plan_id}", "get"),
    ("/api/user/plans/{plan_id}", "put"),
    ("/api/user/plans/{plan_id}", "delete"),
}


def test_routes() -> None:
    paths = app.openapi()["paths"]
    actual = {(path, method) for path, item in paths.items() for method in item}

    missing = EXPECTED - actual
    assert not missing, f"缺少契约接口：{sorted(missing)}"

    unexpected = actual - EXPECTED
    assert not unexpected, f"出现契约外接口：{sorted(unexpected)}"


if __name__ == "__main__":
    test_routes()
    print(f"route contract check passed ({len(EXPECTED)} 个接口)")
