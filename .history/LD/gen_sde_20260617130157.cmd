; CFET SDE structure generated from:
; - guides/[guide1]structure_parameters.md
; - guides/[guide2]build_structure_with_parameters.md
; - rules/cfet_arch.txt
; - rules/layer_rule_1.txt
; - gds/test1_gds.txt
;
; Coordinate convention:
; x: Source-Gate-Drain direction
; y: gate width / channel width direction
; z: vertical stacking direction

(sde:clear)

; ----------------------------------------------------------------------
; Geometry
; ----------------------------------------------------------------------

; Substrate: layer 1 boundary, z = start_z1/end_z2.
(sdegeo:create-cuboid
  (position 0.00000 0.00000 -0.10000)
  (position 0.04200 0.06200 0.00000)
  "Silicon"
  "Substrate_1")

; Common gate: layer 7 gate, material from layer_rule_1.txt.
(sdegeo:create-cuboid
  (position 0.01400 0.01200 0.00000)
  (position 0.02800 0.05100 0.16000)
  "Tungsten"
  "Gate_Common")

; Channels: num_channel = -1, num_channel_lower = 2, num_channel_upeer = 2.
; channel_center_x = 0.021, channel_center_y = 0.0315.
; channel_length = 0.026, channel_width = 0.021.
(sdegeo:create-cuboid
  (position 0.00800 0.02100 0.01200)
  (position 0.03400 0.04200 0.01800)
  "Silicon"
  "ChannelLower_0")

(sdegeo:create-cuboid
  (position 0.00800 0.02100 0.03000)
  (position 0.03400 0.04200 0.03600)
  "Silicon"
  "ChannelLower_1")

(sdegeo:create-cuboid
  (position 0.00800 0.02100 0.10000)
  (position 0.03400 0.04200 0.10600)
  "Silicon"
  "ChannelUpper_0")

(sdegeo:create-cuboid
  (position 0.00800 0.02100 0.11800)
  (position 0.03400 0.04200 0.12400)
  "Silicon"
  "ChannelUpper_1")

; High-k shells: high_k_thickness = 0.002.
; x range is channel_center_x +/- gate_length/2 = 0.0065..0.0355.
(sdegeo:create-cuboid (position 0.00650 0.01900 0.01800) (position 0.03550 0.04400 0.02000) "HfO2" "HighK_ChannelLower_0_Top")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.01000) (position 0.03550 0.04400 0.01200) "HfO2" "HighK_ChannelLower_0_Bot")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.01200) (position 0.03550 0.02100 0.01800) "HfO2" "HighK_ChannelLower_0_Front")
(sdegeo:create-cuboid (position 0.00650 0.04200 0.01200) (position 0.03550 0.04400 0.01800) "HfO2" "HighK_ChannelLower_0_Back")

(sdegeo:create-cuboid (position 0.00650 0.01900 0.03600) (position 0.03550 0.04400 0.03800) "HfO2" "HighK_ChannelLower_1_Top")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.02800) (position 0.03550 0.04400 0.03000) "HfO2" "HighK_ChannelLower_1_Bot")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.03000) (position 0.03550 0.02100 0.03600) "HfO2" "HighK_ChannelLower_1_Front")
(sdegeo:create-cuboid (position 0.00650 0.04200 0.03000) (position 0.03550 0.04400 0.03600) "HfO2" "HighK_ChannelLower_1_Back")

(sdegeo:create-cuboid (position 0.00650 0.01900 0.10600) (position 0.03550 0.04400 0.10800) "HfO2" "HighK_ChannelUpper_0_Top")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.09800) (position 0.03550 0.04400 0.10000) "HfO2" "HighK_ChannelUpper_0_Bot")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.10000) (position 0.03550 0.02100 0.10600) "HfO2" "HighK_ChannelUpper_0_Front")
(sdegeo:create-cuboid (position 0.00650 0.04200 0.10000) (position 0.03550 0.04400 0.10600) "HfO2" "HighK_ChannelUpper_0_Back")

(sdegeo:create-cuboid (position 0.00650 0.01900 0.12400) (position 0.03550 0.04400 0.12600) "HfO2" "HighK_ChannelUpper_1_Top")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.11600) (position 0.03550 0.04400 0.11800) "HfO2" "HighK_ChannelUpper_1_Bot")
(sdegeo:create-cuboid (position 0.00650 0.01900 0.11800) (position 0.03550 0.02100 0.12400) "HfO2" "HighK_ChannelUpper_1_Front")
(sdegeo:create-cuboid (position 0.00650 0.04200 0.11800) (position 0.03550 0.04400 0.12400) "HfO2" "HighK_ChannelUpper_1_Back")

; Inner spacer walls: inner_spacer_thickness = 0.005.
; The walls cover gate y/z bounds and are cut into pieces around channel holes.
(sdegeo:create-cuboid (position 0.00100 0.01200 0.00000) (position 0.00600 0.02100 0.16000) "Si3N4" "InnerSpacer_L_YMin")
(sdegeo:create-cuboid (position 0.00100 0.04200 0.00000) (position 0.00600 0.05100 0.16000) "Si3N4" "InnerSpacer_L_YMax")
(sdegeo:create-cuboid (position 0.00100 0.02100 0.00000) (position 0.00600 0.04200 0.01200) "Si3N4" "InnerSpacer_L_ZGap_0")
(sdegeo:create-cuboid (position 0.00100 0.02100 0.01800) (position 0.00600 0.04200 0.03000) "Si3N4" "InnerSpacer_L_ZGap_1")
(sdegeo:create-cuboid (position 0.00100 0.02100 0.03600) (position 0.00600 0.04200 0.10000) "Si3N4" "InnerSpacer_L_ZGap_2")
(sdegeo:create-cuboid (position 0.00100 0.02100 0.10600) (position 0.00600 0.04200 0.11800) "Si3N4" "InnerSpacer_L_ZGap_3")
(sdegeo:create-cuboid (position 0.00100 0.02100 0.12400) (position 0.00600 0.04200 0.16000) "Si3N4" "InnerSpacer_L_ZGap_4")

(sdegeo:create-cuboid (position 0.03600 0.01200 0.00000) (position 0.04100 0.02100 0.16000) "Si3N4" "InnerSpacer_R_YMin")
(sdegeo:create-cuboid (position 0.03600 0.04200 0.00000) (position 0.04100 0.05100 0.16000) "Si3N4" "InnerSpacer_R_YMax")
(sdegeo:create-cuboid (position 0.03600 0.02100 0.00000) (position 0.04100 0.04200 0.01200) "Si3N4" "InnerSpacer_R_ZGap_0")
(sdegeo:create-cuboid (position 0.03600 0.02100 0.01800) (position 0.04100 0.04200 0.03000) "Si3N4" "InnerSpacer_R_ZGap_1")
(sdegeo:create-cuboid (position 0.03600 0.02100 0.03600) (position 0.04100 0.04200 0.10000) "Si3N4" "InnerSpacer_R_ZGap_2")
(sdegeo:create-cuboid (position 0.03600 0.02100 0.10600) (position 0.04100 0.04200 0.11800) "Si3N4" "InnerSpacer_R_ZGap_3")
(sdegeo:create-cuboid (position 0.03600 0.02100 0.12400) (position 0.04100 0.04200 0.16000) "Si3N4" "InnerSpacer_R_ZGap_4")

; Source/drain epitaxy: sd_overgrowth_y = 0.005,
; sd_overgrowth_z_up = 0.006, sd_overgrowth_z_down = 0.006.
(sdegeo:create-cuboid
  (position 0.00000 0.01600 0.00600)
  (position 0.00100 0.04700 0.04200)
  "SiGe"
  "SD_Lower_Left")

(sdegeo:create-cuboid
  (position 0.04100 0.01600 0.00600)
  (position 0.04200 0.04700 0.04200)
  "SiGe"
  "SD_Lower_Right")

(sdegeo:create-cuboid
  (position 0.00000 0.01600 0.09400)
  (position 0.00100 0.04700 0.13000)
  "Silicon"
  "SD_Upper_Left")

(sdegeo:create-cuboid
  (position 0.04100 0.01600 0.09400)
  (position 0.04200 0.04700 0.13000)
  "Silicon"
  "SD_Upper_Right")

; ----------------------------------------------------------------------
; Contacts
; ----------------------------------------------------------------------

(sdegeo:define-contact-set "Contact_Gate_Common_Top" 4 (color:rgb 1 0 0) "##")
(sdegeo:define-contact-set "Contact_Gate_Common_Bot" 4 (color:rgb 1 0 0) "##")
(sdegeo:set-contact-boundary-faces
  (find-face-id (position 0.02100 0.03150 0.16000))
  "Contact_Gate_Common_Top")
(sdegeo:set-contact-boundary-faces
  (find-face-id (position 0.02100 0.03150 0.00000))
  "Contact_Gate_Common_Bot")

; ----------------------------------------------------------------------
; Doping
; ----------------------------------------------------------------------

(sdedr:define-constant-profile
  "Substrate_Doping"
  "BoronActiveConcentration"
  1e15)
(sdedr:define-constant-profile-region
  "Place_Sub_Doping"
  "Substrate_Doping"
  "Substrate_1")

(sdedr:define-constant-profile
  "SD_Upper_Doping"
  "PhosphorusActiveConcentration"
  2e20)
(sdedr:define-constant-profile-region
  "Place_SD_U_L"
  "SD_Upper_Doping"
  "SD_Upper_Left")
(sdedr:define-constant-profile-region
  "Place_SD_U_R"
  "SD_Upper_Doping"
  "SD_Upper_Right")

(sdedr:define-constant-profile
  "SD_Lower_Doping"
  "BoronActiveConcentration"
  2e20)
(sdedr:define-constant-profile-region
  "Place_SD_L_L"
  "SD_Lower_Doping"
  "SD_Lower_Left")
(sdedr:define-constant-profile-region
  "Place_SD_L_R"
  "SD_Lower_Doping"
  "SD_Lower_Right")

; channel_doping_enable = false, so no channel doping profile is emitted.

; ----------------------------------------------------------------------
; Meshing
; ----------------------------------------------------------------------

(sdedr:define-refinement-size
  "Global_Mesh_Size"
  0.020 0.020 0.020
  0.010 0.010 0.010)
(sdedr:define-refinement-placement
  "Global_Mesh_Place"
  "Global_Mesh_Size"
  (get-body-list))

(sdedr:define-refeval-window
  "Core_Win"
  "Cuboid"
  (position 0.00000 0.00000 0.00000)
  (position 0.04200 0.06200 0.20000))
(sdedr:define-refinement-size
  "Core_Mesh_Size"
  0.002 0.002 0.002
  0.001 0.001 0.001)
(sdedr:define-refinement-placement
  "Core_Mesh_Place"
  "Core_Mesh_Size"
  "Core_Win")

(sde:build-mesh "snmesh" "-a -c boxmethod" "cfet_structure")
