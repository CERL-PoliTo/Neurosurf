using UnityEngine;

public class FiberBehavior : MonoBehaviour
{
    private static readonly int IsActive = Shader.PropertyToID("_IsActive");
    private static readonly int PulseSpeed = Shader.PropertyToID("_PulseSpeed");
    private static readonly int PulseWidth = Shader.PropertyToID("_PulseWidth");
    private static readonly int PulseColor = Shader.PropertyToID("_PulseColor");

    private bool isActive = false;
    private float pulseSpeed;
    private float pulseWidth;
    private Color pulseColor;
    private MaterialPropertyBlock propertyBlock;
    private MeshRenderer meshRenderer;

    private void Awake()
    {
        meshRenderer = GetComponent<MeshRenderer>();
        propertyBlock = new MaterialPropertyBlock();
    }

    private void ApplyActivityState()
    {
        meshRenderer.GetPropertyBlock(propertyBlock);
        propertyBlock.SetFloat(IsActive, isActive ? 1f : 0f);
        propertyBlock.SetFloat(PulseSpeed, pulseSpeed);
        propertyBlock.SetFloat(PulseWidth, pulseWidth);
        propertyBlock.SetColor(PulseColor, pulseColor);
        meshRenderer.SetPropertyBlock(propertyBlock);
    }

    public void Initialize(Material fiberMaterial)
    {
        pulseSpeed = fiberMaterial.GetFloat(PulseSpeed);
        pulseWidth = fiberMaterial.GetFloat(PulseWidth);
        pulseColor = fiberMaterial.GetColor(PulseColor);

        meshRenderer.sharedMaterial = fiberMaterial;
        meshRenderer.sharedMaterial.renderQueue = GameManager.instance.fiberRenderQueue;
        ApplyActivityState();
    }

    public void ActivateFiber()
    {
        isActive = true;
        ApplyActivityState();
    }

    public void DeactivateFiber()
    {
        isActive = false;
        ApplyActivityState();
    }
}
