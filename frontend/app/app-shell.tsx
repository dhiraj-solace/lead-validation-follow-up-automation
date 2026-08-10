"use client";

import { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import FileUploadOutlinedIcon from "@mui/icons-material/FileUploadOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import LocalFireDepartmentOutlinedIcon from "@mui/icons-material/LocalFireDepartmentOutlined";
import MailOutlineOutlinedIcon from "@mui/icons-material/MailOutlineOutlined";
import PsychologyOutlinedIcon from "@mui/icons-material/PsychologyOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import {
  Avatar,
  Box,
  Chip,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography
} from "@mui/material";

const navItems = [
  { label: "Dashboard", href: "/", icon: DashboardOutlinedIcon },
  { label: "Upload", href: "/upload", icon: FileUploadOutlinedIcon },
  { label: "Leads", href: "/leads", icon: AccountTreeOutlinedIcon },
  { label: "High Priority", href: "/high-priority", icon: LocalFireDepartmentOutlinedIcon },
  { label: "Follow-ups", href: "/followups", icon: MailOutlineOutlinedIcon },
  { label: "Agents", href: "/agents", icon: GroupsOutlinedIcon },
  { label: "Templates", href: "/templates", icon: ArticleOutlinedIcon },
  { label: "AI Learning", href: "/learning", icon: PsychologyOutlinedIcon },
  { label: "Settings", href: "/settings", icon: SettingsOutlinedIcon }
];

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <Box
      sx={{
        bgcolor: "background.default",
        minHeight: "100vh"
      }}
    >
      <Box
        component="aside"
        sx={{
          bgcolor: "#0f2f6b",
          color: "common.white",
          display: "flex",
          flexDirection: "column",
          gap: { xs: 2, md: 3 },
          height: { md: "100vh" },
          left: { md: 0 },
          minWidth: 0,
          overflowY: { md: "auto" },
          p: { xs: 2, md: 2.5 },
          position: { xs: "sticky", md: "fixed" },
          top: { xs: 0, md: 0 },
          width: { md: 288 },
          zIndex: 2
        }}
      >
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <Avatar
            variant="rounded"
            sx={{
              bgcolor: "primary.main",
              color: "common.white",
              fontSize: 15,
              fontWeight: 900,
              height: 42,
              width: 42
            }}
          >
            LA
          </Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 900, lineHeight: 1.2 }}>
              Lead Automation
            </Typography>
            <Typography color="#bfdbfe" sx={{ fontSize: 12 }}>
              Validation & follow-up
            </Typography>
          </Box>
        </Stack>

        <List
          component="nav"
          aria-label="Primary navigation"
          sx={{
            display: { xs: "flex", md: "block" },
            gap: { xs: 0.75, md: 0.5 },
            overflowX: { xs: "auto", md: "visible" },
            p: 0
          }}
        >
          {navItems.map(({ label, href, icon: Icon }) => {
            const active = href === "/" ? pathname === href : pathname.startsWith(href);
            return (
              <ListItemButton
                LinkComponent={Link}
                href={href}
                key={href}
                selected={active}
                sx={{
                  borderRadius: 2,
                  color: active ? "#0f2f6b" : "#dbeafe",
                  flex: { xs: "0 0 auto", md: "1 1 auto" },
                  minHeight: 42,
                  px: 1.5,
                  py: 1,
                  "&.Mui-selected": {
                    bgcolor: "common.white",
                    color: "#0f2f6b",
                    fontWeight: 800
                  },
                  "&.Mui-selected:hover": {
                    bgcolor: "common.white"
                  },
                  "&:hover": {
                    bgcolor: "rgba(255,255,255,0.08)",
                    color: "common.white"
                  }
                }}
              >
                <ListItemIcon sx={{ color: "inherit", minWidth: 32 }}>
                  <Icon fontSize="small" />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography noWrap sx={{ fontSize: 14, fontWeight: active ? 800 : 650 }}>
                      {label}
                    </Typography>
                  }
                />
              </ListItemButton>
            );
          })}
        </List>

        <Chip
          color="primary"
          label="Local MVP"
          size="small"
          variant="outlined"
          sx={{
            alignSelf: "flex-start",
            borderColor: "rgba(255,255,255,0.18)",
            color: "#bfdbfe",
            display: { xs: "none", md: "inline-flex" },
            mt: "auto"
          }}
        />
      </Box>

      <Box
        component="main"
        sx={{
          minWidth: 0,
          ml: { md: "288px" },
          p: { xs: 1.5, sm: 2.25, lg: 3 }
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
