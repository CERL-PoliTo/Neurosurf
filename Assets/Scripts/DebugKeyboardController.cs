using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Serialization;
using UnityEngine.UI;

public class DebugKeyboardController : MonoBehaviour
{
    [Header("UI")]
    [SerializeField] private Slider scalpSlider;
    [SerializeField] private Slider skullSlider;
    [SerializeField] private Slider brainSlider;
    [SerializeField] private Toggle scalpToggle;
    [SerializeField] private Toggle skullToggle;
    [SerializeField] private Toggle brainToggle;
    [SerializeField] private Toggle fibersToggle;
    [SerializeField] private Dropdown colormapDropdown;
    
    [Header("Scene Objects")]
    [SerializeField] private Transform xrOrigin;
    [SerializeField] private GameObject brainSurfaces;

    [Header("Input Actions")]
    [SerializeField] private InputActionReference moveXZ;
    [SerializeField] private InputActionReference moveY;
    [SerializeField] private InputActionReference rotateBrain;
    [SerializeField] private InputActionReference nextColormap;

    [SerializeField] private InputActionReference toggleVisibilityScalp;
    [SerializeField] private InputActionReference toggleVisibilitySkull;
    [SerializeField] private InputActionReference toggleVisibilityBrain;
    [SerializeField] private InputActionReference toggleVisibilityFibers;

    [SerializeField] private InputActionReference transparencyScalpPlus;
    [SerializeField] private InputActionReference transparencyScalpMinus;
    [SerializeField] private InputActionReference transparencySkullPlus;
    [SerializeField] private InputActionReference transparencySkullMinus;
    [SerializeField] private InputActionReference transparencyBrainPlus;
    [SerializeField] private InputActionReference transparencyBrainMinus;

    [Header("Movement settings")]
    [SerializeField] private float moveSpeed = 0.2f;
    [SerializeField] private float verticalSpeed = 0.1f;
    [SerializeField] private float rotateSpeed = 36f;
    [FormerlySerializedAs("sliderSpeed")] [SerializeField] private float transparencySliderSpeed = 0.5f;
    
    [Header("Mouse Look")]
    [SerializeField] private InputActionReference lookDelta;
    [SerializeField] private InputActionReference lookEnable;
    [SerializeField] private float lookSensitivity = 0.06f;
    [SerializeField] private float minPitch = -80f;
    [SerializeField] private float maxPitch = 70f;
    [SerializeField] private bool lockCursorWhileLooking = true;

    private Transform xrOriginCamera;
    private float yaw;       
    private float pitch;     
    private bool looking;    

    private void Awake()
    {
        if (xrOrigin is null) return;
        Camera cam = xrOrigin.GetComponentInChildren<Camera>();
        if (cam) xrOriginCamera = cam.transform;
    }

    private void OnEnable()
    {
        EnableAction(nextColormap, OnNextColormap);

        EnableAction(toggleVisibilityScalp, _ => FlipToggle(scalpToggle));
        EnableAction(toggleVisibilitySkull, _ => FlipToggle(skullToggle));
        EnableAction(toggleVisibilityBrain, _ => FlipToggle(brainToggle));
        EnableAction(toggleVisibilityFibers, _ => FlipToggle(fibersToggle));

        EnableAction(transparencyScalpPlus);
        EnableAction(transparencyScalpMinus);
        EnableAction(transparencySkullPlus);
        EnableAction(transparencySkullMinus);
        EnableAction(transparencyBrainPlus);
        EnableAction(transparencyBrainMinus);

        moveXZ.action.Enable();
        moveY.action.Enable();
        rotateBrain.action.Enable();
        
        if (lookDelta)  lookDelta.action.Enable();
        if (lookEnable) lookEnable.action.Enable();

        if (lookEnable)
        {
            lookEnable.action.started += OnLookStarted;
            lookEnable.action.canceled += OnLookCanceled;
        }
        
        if (xrOrigin) yaw = xrOrigin.eulerAngles.y;
        if (xrOriginCamera)  pitch = NormalizePitch(xrOriginCamera.localEulerAngles.x);
    }

    private void OnDisable()
    {
        DisableAction(nextColormap, OnNextColormap);

        DisableAction(toggleVisibilityScalp);
        DisableAction(toggleVisibilitySkull);
        DisableAction(toggleVisibilityBrain);
        DisableAction(toggleVisibilityFibers);

        DisableAction(transparencyScalpPlus);
        DisableAction(transparencyScalpMinus);
        DisableAction(transparencySkullPlus);
        DisableAction(transparencySkullMinus);
        DisableAction(transparencyBrainPlus);
        DisableAction(transparencyBrainMinus);

        moveXZ.action.Disable();
        moveY.action.Disable();
        rotateBrain.action.Disable();
        
        if (lookEnable)
        {
            lookEnable.action.started -= OnLookStarted;
            lookEnable.action.canceled -= OnLookCanceled;
            lookEnable.action.Disable();
        }
        if (lookDelta) lookDelta.action.Disable();

        if (!lockCursorWhileLooking || !looking) return;
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = false;
        looking = false;
    }

    private void Update()
    {
        float dt = Time.deltaTime;

        // movement
        Vector2 mxz = moveXZ.action.ReadValue<Vector2>();
        float my = moveY.action.ReadValue<float>();
        xrOrigin.Translate(
            new Vector3(mxz.x * moveSpeed, my * verticalSpeed, mxz.y * moveSpeed) * dt,
            Space.Self
        );

        // model rotation
        if (brainSurfaces is not null)
        {
            float rotInput = rotateBrain.action.ReadValue<float>();
            if (Mathf.Abs(rotInput) > 0.001f)
                brainSurfaces.transform.Rotate(0f, rotInput * rotateSpeed * dt, 0f, Space.World);
        }

        // transparency sliders
        ApplySliderDelta(scalpSlider, transparencyScalpPlus.action.ReadValue<float>() - transparencyScalpMinus.action.ReadValue<float>(), dt);
        ApplySliderDelta(skullSlider, transparencySkullPlus.action.ReadValue<float>() - transparencySkullMinus.action.ReadValue<float>(), dt);
        ApplySliderDelta(brainSlider, transparencyBrainPlus.action.ReadValue<float>() - transparencyBrainMinus.action.ReadValue<float>(), dt);
        
        // mouse look
        if (!looking || lookDelta is null) return;
        Vector2 d = lookDelta.action.ReadValue<Vector2>(); // pixels since last frame
        yaw   += d.x * lookSensitivity;
        pitch -= d.y * lookSensitivity;
        pitch  = Mathf.Clamp(pitch, minPitch, maxPitch);

        if (xrOrigin) xrOrigin.rotation = Quaternion.Euler(0f, yaw, 0f);
        if (xrOriginCamera)  xrOriginCamera.localRotation = Quaternion.Euler(pitch, 0f, 0f);
    }

    // helper methods
    private void ApplySliderDelta(Slider s, float signedHold, float dt)
    {
        if (s is null || Mathf.Approximately(signedHold, 0f)) return;
        float v = Mathf.Clamp(s.value + signedHold * transparencySliderSpeed * dt, s.minValue, s.maxValue);
        s.value = v; // will fire OnValueChanged
    }

    private void OnNextColormap(InputAction.CallbackContext _)
    {
        if (colormapDropdown is null || colormapDropdown.options.Count == 0) return;
        int idx = Mathf.Max(0, colormapDropdown.value);
        idx = (idx + 1) % colormapDropdown.options.Count;
        colormapDropdown.value = idx;
        colormapDropdown.RefreshShownValue();
    }

    private void FlipToggle(Toggle t)
    {
        if (t is null) return;
        t.isOn = !t.isOn;
    }

    // input action utils
    private static void EnableAction(InputActionReference ar, System.Action<InputAction.CallbackContext> handler = null)
    {
        if (ar is null) return;
        ar.action.Enable();
        if (handler is not null) ar.action.performed += handler;
    }

    private static void DisableAction(InputActionReference ar, System.Action<InputAction.CallbackContext> handler = null)
    {
        if (ar is null) return;
        if (handler is not null) ar.action.performed -= handler;
        ar.action.Disable();
    }
    
    private void OnLookStarted(InputAction.CallbackContext _)
    {
        looking = true;
        if (!lockCursorWhileLooking) return;
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;
    }

    private void OnLookCanceled(InputAction.CallbackContext _)
    {
        looking = false;
        if (lockCursorWhileLooking)
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
    }

    private static float NormalizePitch(float xDeg)
    {
        // convert from [0, 360) to [-180, 180); then use as pitch basis
        if (xDeg > 180f) xDeg -= 360f;
        return xDeg;
    }
}
