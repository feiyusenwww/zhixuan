declare namespace Zhixuan {
 interface ApiResponse<T>{code:number;message:string;data:T;trace_id:string}
 interface Citation{source_name:string;source_url:string;year:number}
 interface User{user_id:string;username:string}
 interface AuthResult extends User{access_token:string}
 interface ProfilePreferences{priority?:'城市优先'|'专业优先';preferred_majors?:string[];preferred_cities?:string[];accept_adjustment?:boolean}
 interface Profile{
  province:string;score:number;subject_type:string;
  household_type?:'农村'|'城镇';
  household_county?:string;enrollment_county?:string;
  household_years?:number;enrollment_years?:number;
  parent_household_local?:boolean;special_marks?:string[];
  preferences?:ProfilePreferences;updated_at?:string;
 }
 interface Eligibility{eligible:string[];pending:string[];ineligible:string[];profile:Profile;citations:Citation[]}
 interface QaResult{answer:string;confidence:number;citations:Citation[]}
 interface Pathway extends Citation{id:string;name:string;status:string;category?:string;priority?:'P0'|'P1'|'P2'}
 interface RegionCheck{in_region:boolean;region_name:string|null;citations:Citation[]}
 interface PlanItem extends Citation{school_id:string;name:string;tier:'冲'|'稳'|'保';risk_level:'low'|'medium'|'high'}
 interface PlanRequest{profile:Profile;strategy:'冲'|'稳'|'保';priority?:'城市优先'|'专业优先';preferred_majors?:string[];preferred_cities?:string[];accept_adjustment?:boolean}
 interface PlanResult{
  items:PlanItem[];risk_notes:string[];citations:Citation[];
  strategy?:string;priority?:string;tiers?:Record<string,PlanItem[]>;
  quota?:string[];shortage?:string[];excluded?:string[];
  risks?:string[];summary?:string;data_status?:string;disclaimer?:string;
 }
 interface School extends Citation{school_id:string;name:string;province:string}
}
