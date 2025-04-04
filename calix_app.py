with st.form("device_form"):
    device_name = st.text_input("Enter device model name ℹ️", help="Found in the Description column of your file")
    load_defaults = st.form_submit_button("🔍 Look Up Device")

    default_type = "ONT"
    default_port = ""
    default_profile_id = ""
    default_password = "no value"
    device_found = False

    # Look up device and set defaults
    if load_defaults:
        st.session_state.device_lookup = {"device_name": device_name, "warning_shown": False}
        
        # Normalize the device name to uppercase to match keys in the mapping
        device_name = device_name.upper()

        # Check if the device exists in the mapping
        if device_name in device_profile_name_map:
            device_found = True
            default_type = device_profile_name_map[device_name]
            template = device_numbers_template_map.get(device_name, "")

            # Check if template is valid
            if not template:
                st.error(f"❌ No template found for the device: {device_name}. Please check if this device is supported or contact support.")
            else:
                match_port = re.search(r"ONT_PORT=([^|]*)", template)
                match_profile = re.search(r"ONT_PROFILE_ID=([^|]*)", template)
                default_port = match_port.group(1) if match_port else ""
                default_profile_id = match_profile.group(1) if match_profile else ""

    device_types = ["ONT", "ROUTER", "MESH", "SFP", "ENDPOINT"]
    mapped_type = device_profile_name_map.get(device_name)
    default_index = device_types.index(mapped_type) if mapped_type in device_types else 0
    selected_index = st.selectbox("What type of device is this? ℹ️", device_types, index=default_index if load_defaults else 0, key="device_type_selector", help="Make sure this matches how your system provisions this device")
    device_type = selected_index if isinstance(selected_index, str) else device_types[default_index]

    # If device not found and selected as ONT
    if load_defaults and not device_found and device_type == "ONT":
        st.warning("🚧 This device model name was not found in memory. You can still proceed as ONT by providing required settings.\n\nPlease provide the `ONT_PORT` and `ONT_PROFILE_ID` based on how it's setup in your system.\nIf this device is not in your Camvio inventory, it may fail provisioning. Please contact Camvio Support to add it.")

    # Warning when device type doesn't match the default mapping
    if load_defaults and device_name in device_profile_name_map:
        mapped_type = device_profile_name_map[device_name]
        if mapped_type != device_type:
            st.warning(f"⚠️ This device is typically identified as `{mapped_type}` in the system. You're using `{device_type}`, so please verify that your provisioning system is set up to handle this device type.")
    
    # If device type is ONT, make sure the user is aware of the provisioning concerns
    if device_type == "ONT" and mapped_type != device_type:
        st.warning("⚠️ Ensure that your provisioning system is set up for this ONT device type. If not, it may fail during provisioning.")

    location = st.selectbox("Where should it be stored? ℹ️", ["WAREHOUSE", "Custom..."], help="Camvio must have this location EXACTLY as shown. Case and spelling matter.")
    if location == "Custom...":
        location = st.text_input("Enter custom location (must match Camvio EXACTLY)")
        st.warning("⚠️ This must exactly match the spelling/case in Camvio or it will fail.")

    custom_ont_port = st.text_input("ONT_PORT ℹ️", value=default_port, help="The interface this ONT uses to connect (e.g., G1 or x1)")
    custom_profile_id = st.text_input("ONT_PROFILE_ID ℹ️", value=default_profile_id or device_name, help="Provisioning profile used in your system")

    # Ensure the profile ID is uppercase
    if custom_profile_id:
        custom_profile_id = custom_profile_id.upper()

    add_device = st.form_submit_button("➕ Add Device")

    # Ensure custom fields are correctly added to devices
    if add_device and device_name:
        st.session_state.devices.append({
            "device_name": device_name.strip(),
            "device_type": device_type,
            "location": location.strip(),
            "ONT_PORT": custom_ont_port.strip() if device_type == "ONT" else "",
            "ONT_PROFILE_ID": custom_profile_id.strip() if device_type == "ONT" else "",
            "ONT_MOMENTUM_PASSWORD": "NO VALUE"
        })

if st.session_state.devices:
    st.markdown("\n")
    st.write("### Devices Selected:")
    for i, d in enumerate(st.session_state.devices):
        cols = st.columns([5, 1])
        with cols[0]:
            st.write(f"🔹 {d['device_name']} → {d['device_type']} @ {d['location']}")
            if d["device_type"] == "ONT":
                st.code(f"ONT_PORT: {d['ONT_PORT']}\nONT_PROFILE_ID: {d['ONT_PROFILE_ID']}\nONT_MOMENTUM_PASSWORD: NO VALUE", language="text")
        with cols[1]:
            if st.button("🗑️ Remove", key=f"remove_{i}"):
                st.session_state.devices.pop(i)
                st.rerun()
