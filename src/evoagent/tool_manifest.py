from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolManifest:
 action:str;policy_tool:str;reversible:bool=True;filesystem_scope:tuple[str,...]=();network_scope:tuple[str,...]=();estimated_cost:float=0.0

DEFAULT_TOOL_MANIFESTS={
 'dispatch':ToolManifest('dispatch','query'),
 'paper_search':ToolManifest('paper_search','query'),
 'paper_search_broad':ToolManifest('paper_search_broad','query'),
 'research_synthesis':ToolManifest('research_synthesis','query'),
 'claim_validation':ToolManifest('claim_validation','inspect'),
 'code_analysis':ToolManifest('code_analysis','inspect'),
 'model_fallback':ToolManifest('model_fallback','external_api',network_scope=('model-provider',),estimated_cost=.01),
 'human_approval':ToolManifest('human_approval','query'),
 'code_sandbox':ToolManifest('code_sandbox','shell',reversible=False),
 'unit_tests':ToolManifest('unit_tests','write_file'),
}
