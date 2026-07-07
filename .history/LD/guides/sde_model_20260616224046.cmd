(sde:clear)
(sde:set-process-up-direction "+z")
(sdegeo:set-default-boolean "ABA")

; (1). Parameters
; Design parameter
(define LSD 0.015)
(define LSD_extension 0.01)
(define Lg 0.01)
(define R 0.004)
(define TSiO2 1e-3)
(define THfO2 1e-3)
(define HSDC 0.015)
(define Hsub 0.05)
(define Hsti 0.05)
(define Wsti 0.01)
(define Hbuf 2e-3)
(define Hmetal 3e-3)
(define fillter_cs 4e-3)

; Derived quantities
(define RSiO2 (+ R (* 2 TSiO2)))
(define RHfO2 (+ RSiO2 (* 2 THfO2)))

; x-Coordinate
(define x1 LSD)
(define x2 (+ x1 LSD_extension))
(define x3 (+ x2 Lg))
(define x4 (+ x3 LSD_extension))
(define x5 (+ x4 LSD))

; y-Coordinate
(define y1 (+ (* 2 R) (* 2 Wsti)))
(define y2 Wsti)
(define y3 (+ y2 (* 2 R)))
(define y4 (/ (+ y2 y3) 2))

; z-Coordinate
(define z1 (+ Hsub Hsti))
(define z2 Hsub)
(define z3 (+ z1 Hbuf))
(define z4 (+ z3 HSDC))
(define z5 (- z4 R))
(define z6 (+ (+ z5 RHfO2) Hmetal))

; Doping info
(define C_Doping 1e17)
(define SD_ext_Doping 8e19)
(define SD_Doping 8e19)
(define Sub_Doping 1e17)
(define SD_dopant "ArsenicActiveConcentration")
(define substrate_dopant "BoronActiveConcentration")

; (2). Structure
; Si substrate
(sdegeo:create-cuboid (position 0 0 0) (position x5 y1 z1) "Silicon" "R.Body")

; STI SiO2
(sdegeo:create-cuboid (position 0 0 z2) (position x5 y2 z1) "SiO2" "R.STI_1")
(sdegeo:create-cuboid (position 0 y3 z2) (position x5 y1 z1) "SiO2" "R.STI_2")

; SiO2 Buffer
(sdegeo:create-cuboid (position x2 0 z1) (position x3 y1 z3) "SiO2" "R.Buffer")

; Source/Source Extension
(sdegeo:create-cuboid (position 0 y2 z1) (position x1 y3 z4) "Silicon" "R.Source")
(sdegeo:create-cylinder (position x1 y4 z5) (position x2 y4 z5) R "Silicon" "R.SourceExt")

; Channel
(sdegeo:create-cylinder (position x2 y4 z5) (position x3 y4 z5) R "Silicon" "R.Channel")

; Drain/Drain Extension
(sdegeo:create-cuboid (position x4 y2 z1) (position x5 y3 z4) "Silicon" "R.Drain")
(sdegeo:create-cylinder (position x3 y4 z5) (position x4 y4 z5) R "Silicon" "R.DrainExt")

; Fillet for source and drain
(define sd_edge_list (list
    (car (find-edge-id (position (/ x1 2) y2 z4)))
    (car (find-edge-id (position (/ x1 2) y3 z4)))
    (car (find-edge-id (position (/ (+ x4 x5) 2) y2 z4)))
    (car (find-edge-id (position (/ (+ x4 x5) 2) y3 z4)))
))

(sdegeo:fillet sd_edge_list R)

; Gate Oxide SiO2
(sdegeo:set-default-boolean "BAB")
(sdegeo:create-cylinder (position x2 y4 z5) (position x3 y4 z5) RSiO2 "SiO2" "R.Oxide_1")

; Gate Oxide HfO2
(sdegeo:create-cylinder (position x2 y4 z5) (position x3 y4 z5) RHfO2 "HfO2" "R.Oxide_2")

; Gate Contact Metal
(sdegeo:create-cuboid (position x2 0 z3) (position x3 y1 z6) "Tungsten" "R.Gate")

; S/D Contact Metal
(sdegeo:create-cuboid (position 0 0 z2) (position x1 y1 z6) "Tungsten" "R.Source_contact")
(sdegeo:create-cuboid (position x4 0 z2) (position x5 y1 z6) "Tungsten" "R.Drain_contact")

; S/D Spacer Insulator
(sdegeo:create-cuboid (position x1 0 z2) (position x2 y1 z6) "Si3N4" "R.Source_spacer_insulator")
(sdegeo:create-cuboid (position x3 0 z2) (position x4 y1 z6) "Si3N4" "R.Drain_spacer_insulator")

; Fillet for the contact and spacer insulator 
(define cs_edge_list (list 
    (car (find-edge-id (position (/ x1 2) 0 z6)))
    (car (find-edge-id (position (/ (+ x2 x1) 2) 0 z6)))
    (car (find-edge-id (position (/ (+ x3 x2) 2) 0 z6)))
    (car (find-edge-id (position (/ (+ x4 x3) 2) 0 z6)))
    (car (find-edge-id (position (/ (+ x5 x4) 2) 0 z6)))
    (car (find-edge-id (position (/ x1 2) y1 z6)))
    (car (find-edge-id (position (/ (+ x2 x1) 2) y1 z6)))
    (car (find-edge-id (position (/ (+ x3 x2) 2) y1 z6)))
    (car (find-edge-id (position (/ (+ x4 x3) 2) y1 z6)))
    (car (find-edge-id (position (/ (+ x5 x4) 2) y1 z6)))
))

(sdegeo:fillet cs_edge_list fillter_cs)

; (3). Contact
; Source
(sdegeo:set-contact (find-face-id (position (/ x1 2) (/ y1 2) z6)) "source")

; Drain
(sdegeo:set-contact (find-face-id (position (/ (+ x4 x5) 2) (/ y1 2) z6)) "drain")

; Gate
(sdegeo:set-contact (find-face-id (position (/ (+ x2 x3) 2) (/ y1 2) z6)) "gate")

; Substrate
(sdegeo:set-contact (find-face-id (position (/ x5 2) (/ y1 2) 0)) "substrate")

; (4). Doping
; Source Doping
(sdedr:define-constant-profile "DP.source" SD_dopant SD_Doping)
(sdedr:define-constant-profile-region "DPP.source" "DP.source" "R.Source" )
(sdedr:define-constant-profile "DP.source_ext" SD_dopant SD_ext_Doping)
(sdedr:define-constant-profile-region "DPP.source_ext" "DP.source_ext" "R.SourceExt" )

; Drain Doping
(sdedr:define-constant-profile "DP.Drain" SD_dopant SD_Doping)
(sdedr:define-constant-profile-region "DPP.Drain" "DP.Drain" "R.Drain" )
(sdedr:define-constant-profile "DP.Drain_ext" SD_dopant SD_ext_Doping)
(sdedr:define-constant-profile-region "DPP.Drain_ext" "DP.Drain_ext" "R.DrainExt" )

; Channel Doping
(sdedr:define-constant-profile "DP.Channel" substrate_dopant C_Doping)
(sdedr:define-constant-profile-region "DPP.Channel" "DP.Channel" "R.Channel" )

; Substrate Doping
(sdedr:define-constant-profile "DP.Body" substrate_dopant Sub_Doping)
(sdedr:define-constant-profile-region "DPP.Body" "DP.Body" "R.Body" )

; (5). Mesh
; Globel mesh
(define gf_max 2)
(define gf_min 4)
(define all_list (get-body-list))

(sdedr:define-refeval-window
    "Rwin.global" 
    "cuboid"
    (position (sde:max-x all_list) (sde:max-y all_list) (sde:max-z all_list))
    (position (sde:min-x all_list) (sde:min-y all_list) (sde:min-z all_list))
)

(sdedr:define-refinement-size "RD.global"
    (/ Lg gf_max) (/ (/ y1 2) gf_max) (/ (/ Hsub 2) gf_max)
    (/ Lg gf_min) (/ (/ y1 2) gf_min) (/ (/ Hsub 2) gf_min)
)

(sdedr:define-refinement-placement "RP.global" "RD.global" "Rwin.global")

; Channel mesh
(define chf_max 4)
(define chf_min 8)

(sdedr:define-refinement-size "RD.channel" 
    (/ Lg chf_max) (/ (* 2 R) chf_max) (/ (* 2 R) chf_max) 
    (/ Lg chf_min) (/ (* 2 R) chf_min) (/ (* 2 R) chf_min) 
)
(sdedr:define-refinement-region "RP.channel" "RD.channel" "R.Channel")

; S/D Extension mesh
(define SDextf_max 4)
(define SDextf_min 8)

(sdedr:define-refinement-size "RD.extention" 
    (/ LSD_extension SDextf_max) (/ (* 2 R) SDextf_max) (/ (* 2 R) SDextf_max) 
    (/ LSD_extension SDextf_min) (/ (* 2 R) SDextf_min) (/ (* 2 R) SDextf_min) 
)

(sdedr:define-refinement-region "RP.Source_extention" "RD.extention" "R.SourceExt")
(sdedr:define-refinement-region "RP.Drain_extention" "RD.extention" "R.DrainExt")

; Substrate/Buffer interface
(define intf_max 4)
(define intf_min 8)
(sdedr:define-refeval-window
    "Rwin.sub_buf"
    "cuboid"
    (position 0 y2 z1) 
    (position x5 y3 (- z1 (* 0.1 z1)))
)

(sdedr:define-refinement-size "RD.sub_buf" 
    (/ (* 2 Lg) intf_max) (/ (* 2 R) intf_max) (/ (/ Hsub 2) intf_max) 
    (/ (* 2 Lg) intf_min) (/ (* 2 R) intf_min) (/ (/ Hsub 2) intf_min) 
)

(sdedr:define-refinement-function 
    "RD.sub_buf"
    "MaxLenInt" 
    "R.Body"
    "R.Drain"
    1.5e-3
    1.5
    "UseRegionNames"
    "DoubleSide"
)

(sdedr:define-refinement-function 
    "RD.sub_buf"
    "MaxLenInt" 
    "R.Body"
    "R.Source"
    1.5e-3
    1.5
    "UseRegionNames"
    "DoubleSide"
)

(sdedr:define-refinement-function 
    "RD.sub_buf"
    "MaxLenInt" 
    "Silicon"
    "SiO2"
    1.5e-3
    1.5
)

(sdedr:define-refinement-function 
    "RD.sub_buf"
    "MaxLenInt" 
    "Silicon"
    "Si3N4"
    1.5e-3
    1.5
)

(sdedr:define-refinement-placement "RP.sub_buf" "RD.sub_buf" "Rwin.sub_buf")

; Apply Offset meshing between channel and dielectric layer
(sdedr:offset-block "region" "R.Channel" "maxlevel" 5)
(sdedr:offset-interface "region" "R.Channel" "R.Oxide_1" "hlocal" 1e-3 "factor" 1.2)


; (6). Save
(sde:build-mesh "n@node@_msh.tdr")