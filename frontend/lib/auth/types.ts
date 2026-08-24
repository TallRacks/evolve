export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface Membership {
  id: string;
  organization: Organization;
  role: "owner" | "admin" | "manager" | "member" | "artist";
  permissions: string[];
}

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_superuser: boolean;
}

export interface SessionBootstrap {
  user: AuthUser;
  memberships: Membership[];
}
